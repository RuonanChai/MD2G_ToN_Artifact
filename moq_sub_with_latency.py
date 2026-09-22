import sys
import time
import subprocess
import os
import threading
import signal
import re


def canonical_subscriber_url(url: str, broadcast_name: str | None = None) -> tuple[str, str | None]:
    """Return (sub_url, broadcast_name) matching the publisher /anon/ prefix.

    Retry must reuse this URL. Never strip an existing /anon/ path down to /.
    """
    if url and not url.startswith("http"):
        url = "https://" + url
    if broadcast_name:
        url_match = re.match(r"(https?://[^/]+)(/.*)?", url)
        if url_match:
            base_host = url_match.group(1)
            existing_path = url_match.group(2) if url_match.group(2) else ""
            if existing_path and existing_path not in ("/", ""):
                return url, broadcast_name
            return f"{base_host}/anon/", broadcast_name
        sub_url = url.rstrip("/") + "/" if url and not url.endswith("/") else url
        return sub_url, broadcast_name
    url_match = re.match(r"https?://[^/]+/([^/?]+)", url or "")
    if url_match:
        extracted = url_match.group(1).split("?")[0]
        return (url or "").split("?")[0], extracted
    return (url.rstrip("/") + "/base" if url else url), "base"

# ✅ 【关键修复】设置 sys.stdout 为无缓冲模式，确保数据及时传递给父进程
# 问题：如果输出被重定向到管道，sys.stdout 可能是全缓冲的，导致数据延迟传递
# 解决：使用二进制模式，并确保及时刷新
if hasattr(sys.stdout, 'reconfigure'):
    # Python 3.7+ 支持 reconfigure
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except:
        pass

# ✅ 【方案2：订阅重试机制】全局变量用于控制重试
retry_enabled = True
max_retries = 5
retry_backoff_base = 2.0  # 指数退避基数
MIN_THRESHOLD = 100  # 最小数据阈值（100字节，用于检测是否收到数据）


def should_restart_dead_subscriber(poll_returncode, dump_bytes: int) -> bool:
    """Retry only a dead subscriber. Never kill a live /anon/ subscribe for slow first byte."""
    if poll_returncode is None:
        return False
    try:
        n = int(dump_bytes or 0)
    except (TypeError, ValueError):
        n = 0
    return n < MIN_THRESHOLD

def monitor_dump_file(dump_file, log_file, start_time, process_ref=None, binary=None, track_name=None, url=None, pub_log_file=None, broadcast_name=None):
    """
    监控 dump 文件。
    只有当文件大小超过 4KB (4096 bytes) 时，才视为'首帧到达'。
    这样可以过滤掉文件创建时的 0 字节或握手产生的微量数据。
    
    ✅ 【方案2：订阅重试机制】如果5秒内没有收到有效数据，强制断开并重新发起订阅
    """
    timeout = 30
    poll_interval = 0.1  # 100ms 精度（降低CPU占用）
    elapsed = 0
    # 阈值：4KB (Base 帧通常 > 10KB，握手包通常 < 2KB)
    THRESHOLD = 4096 
    
    last_receive_time = start_time
    last_total_bytes = 0
    retry_count = 0
    
    # ✅ 【方案2：订阅重试机制】使用列表引用，确保可以修改外部process对象
    if process_ref is None:
        process_ref = [None]
    
    while elapsed < timeout:
        if os.path.exists(dump_file):
            try:
                size = os.path.getsize(dump_file)
                if size > THRESHOLD:
                    # 💥 捕捉到有效视频数据！
                    arrival_time = time.time()
                    latency_ms = (arrival_time - start_time) * 1000.0
                    
                    # 写入 CSV 格式: start_time, arrival_time, latency_ms
                    with open(log_file, "w") as f:
                        f.write(f"{start_time},{arrival_time},{latency_ms:.2f}\n")
                    return
                
                # ✅ 【方案2：订阅重试机制】检测数据增长
                if size > last_total_bytes:
                    last_receive_time = time.time()
                    last_total_bytes = size
            except:
                pass
        
        # Retry ONLY if the subscriber already died. Never kill a live /anon/ session
        # because dump bytes are still below MIN_THRESHOLD.
        if retry_enabled and process_ref[0] is not None and binary is not None and track_name is not None and url is not None:
            time_since_last_receive = time.time() - last_receive_time
            live_rc = None
            try:
                live_rc = process_ref[0].poll()
            except Exception:
                live_rc = None
            if (
                time_since_last_receive > 5.0
                and last_total_bytes < MIN_THRESHOLD
                and retry_count < max_retries
                and should_restart_dead_subscriber(live_rc, last_total_bytes)
            ):
                # Process already dead; do not terminate a live subscribe.
                
                # 指数退避
                backoff_time = retry_backoff_base ** retry_count
                time.sleep(backoff_time)
                
                # 重新发起订阅
                retry_count += 1
                with open(pub_log_file, "a", errors="ignore") as f:
                    f.write(f"\n[RETRY {retry_count}/{max_retries}] Re-subscribing after {backoff_time:.1f}s backoff...\n")
                
                retry_broadcast_name = broadcast_name if broadcast_name else "base"
                # Retry MUST reuse the same /anon/ URL as the initial subscribe.
                # Stripping /anon/ to "/" fails auth and leaves dump_bytes=0 / decoded_state=None.
                retry_sub_url, retry_broadcast_name = canonical_subscriber_url(
                    url, retry_broadcast_name
                )
                
                cmd = [
                    binary,
                    "--url", retry_sub_url,  # ✅ 使用包含路径的URL，与Publisher一致
                    "--broadcast", retry_broadcast_name,  # ✅ broadcast名称（与URL路径一致）
                    "--track", track_name,  # ✅ track名称
                    "--dump", dump_file,  # ✅ dump文件
                    "--tls-disable-verify"  # ✅ 禁用TLS验证
                ]
                
                try:
                    # ✅ 【关键修复】重试时也使用 PIPE 模式，与初始启动保持一致
                    # 这样父进程的 DataDrainer 可以读取数据
                    retry_log_file = open(pub_log_file, "ab")  # 二进制追加模式
                    process_ref[0] = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,  # ✅ 使用 PIPE，让父进程可以读取
                        stderr=subprocess.STDOUT,  # ✅ 合并 stderr 到 stdout
                        bufsize=0  # ✅ 关键：关闭系统级缓冲
                    )
                    
                    # ✅ 【关键修复】启动后台线程，将重试进程的输出写入日志文件
                    def write_retry_to_log():
                        try:
                            while True:
                                data = process_ref[0].stdout.read(4096)
                                if not data:
                                    if process_ref[0].poll() is not None:
                                        break
                                    time.sleep(0.01)
                                    continue
                                retry_log_file.write(data)
                                retry_log_file.flush()
                        except:
                            pass
                        finally:
                            try:
                                retry_log_file.close()
                            except:
                                pass
                    
                    retry_log_thread = threading.Thread(target=write_retry_to_log, daemon=True)
                    retry_log_thread.start()
                    
                    last_receive_time = time.time()  # 重置接收时间
                except Exception as e:
                    try:
                        with open(pub_log_file, "a", errors="ignore") as f:
                            f.write(f"\n[RETRY ERROR] Failed to re-subscribe: {str(e)}\n")
                    except:
                        pass
        
        time.sleep(poll_interval)
        elapsed += poll_interval

def main():
    # 参数解析
    # 参数格式：binary, track_name, url, output_file, pub_log_file, latency_log, [start_time], [broadcast_name]
    if len(sys.argv) < 7:
        return

    binary = sys.argv[1]
    track_name = sys.argv[2]
    url = sys.argv[3]
    output_file = sys.argv[4]
    pub_log_file = sys.argv[5]
    latency_log = sys.argv[6]
    
    try:
        start_time_arg = float(sys.argv[7]) if len(sys.argv) > 7 else time.time()
    except:
        start_time_arg = time.time()
    
    # ✅ 【关键修复】支持通过参数传递 broadcast 名称
    # 如果提供了 broadcast 名称参数（第8个参数），使用它；否则从 URL 中提取
    broadcast_name = None
    if len(sys.argv) > 8:
        broadcast_name = sys.argv[8]

    # 修正 URL 格式
    if not url.startswith("http"):
        url = "https://" + url

    sub_url, broadcast_name = canonical_subscriber_url(url, broadcast_name)

    # ✅ 【关键修复】使用 moq-sub 的正确格式：--url --broadcast --track --dump
    # ✅ 【关键】URL路径必须与Publisher一致（如 https://r0.local:4443/base）
    # 根据实际测试，moq-sub需要：
    # - --url <URL> (包含路径，如 https://r0.local:4443/base，与Publisher一致)
    # - --broadcast <BROADCAST> (broadcast名称，如 base，与URL路径一致)
    # - --track <TRACK> (track名称，如 video1)
    # - --dump <DUMP> (输出文件)
    # - --tls-disable-verify (禁用TLS验证)
    cmd = [
        binary,
        "--url", sub_url,  # ✅ 使用包含路径的URL，与Publisher一致（如 https://r0.local:4443/base）
        "--broadcast", broadcast_name,  # ✅ broadcast名称（与URL路径一致）
        "--track", track_name,  # ✅ track名称
        "--dump", output_file,  # ✅ dump文件
        "--tls-disable-verify"  # ✅ 禁用TLS验证
    ]

    # ✅ 【关键修复】使用 PIPE 模式，让输出传递给父进程（dispatch_strategy_enhanced_unified.py）
    # 同时将输出写入日志文件，确保日志可追溯
    # 问题：之前直接写入文件，导致父进程的 DataDrainer 无法读取数据（读取到 0 字节）
    # 解决：使用 PIPE 捕获输出，启动线程同时写入日志文件和 sys.stdout（传递给父进程）
    process_ref = [None]
    log_file_handle = None
    try:
        # ✅ 【关键修复】打开日志文件用于写入
        log_file_handle = open(pub_log_file, "ab")  # append; never truncate scientific gst logs
        
        # ✅ 【关键修复】使用 PIPE 捕获 moq-sub 的输出
        # 这样父进程（dispatch_strategy_enhanced_unified.py）的 DataDrainer 可以读取数据
        process_ref[0] = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,  # ✅ 使用 PIPE，让父进程可以读取
            stderr=subprocess.STDOUT,  # ✅ 合并 stderr 到 stdout
            bufsize=0  # ✅ 关键：关闭系统级缓冲，让数据直接流出
        )
        
        # ✅ 【关键修复】启动后台线程，将 PIPE 中的数据同时写入日志文件和 sys.stdout（传递给父进程）
        def tee_output():
            """将进程输出同时写入日志文件和 sys.stdout（传递给父进程）"""
            try:
                while True:
                    data = process_ref[0].stdout.read(4096)
                    if not data:
                        if process_ref[0].poll() is not None:
                            break
                        time.sleep(0.01)
                        continue
                    # 同时写入日志文件和 sys.stdout（传递给父进程）
                    log_file_handle.write(data)
                    log_file_handle.flush()
                    sys.stdout.buffer.write(data)  # ✅ 传递给父进程
                    sys.stdout.buffer.flush()
            except Exception as e:
                try:
                    with open(pub_log_file, "a", errors="ignore") as f:
                        f.write(f"\n[ERROR] Tee thread error: {e}\n")
                except:
                    pass
            finally:
                try:
                    log_file_handle.close()
                except:
                    pass
        
        tee_thread = threading.Thread(target=tee_output, daemon=True)
        tee_thread.start()
        
        # ✅ 【关键修复】不要立即关闭文件句柄，让它在进程运行期间保持打开
        # 文件句柄会在 tee 线程中关闭
    except Exception as e:
        if log_file_handle:
            log_file_handle.close()
        try:
            with open(pub_log_file, "a") as f:
                f.write(f"\n[FATAL] Failed to start process: {str(e)}\n")
        except:
            pass
        return

    # 启动监控线程 (传入真实的启动时间和进程对象引用用于重试)
    # 注意：这里我们以 python 脚本启动为 T0，或者由主控脚本传入的 T0
    # ✅ 【关键修复】传递 broadcast_name 供重试时使用
    monitor_thread = threading.Thread(
        target=monitor_dump_file, 
        args=(output_file, latency_log, start_time_arg, process_ref, binary, track_name, sub_url, pub_log_file, broadcast_name)
    )
    monitor_thread.daemon = True
    monitor_thread.start()
    
    # 等待监控线程完成（或超时）
    monitor_thread.join(timeout=35)  # 比监控超时时间稍长
    
    # ✅ 【关键修复】保持进程运行，将 moq-sub 的输出传递给父进程
    # 父进程（dispatch_strategy_enhanced_unified.py）的 DataDrainer 会持续读取
    # tee 线程已经在后台运行，将输出同时写入日志和传递给父进程
    if process_ref[0] is not None:
        try:
            # 等待进程结束（tee 线程会持续将输出传递给父进程）
            process_ref[0].wait()
        except:
            pass

if __name__ == "__main__":
    main()
