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

if hasattr(sys.stdout, 'reconfigure'):
    # Python 3.7+ reconfigure
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except:
        pass

retry_enabled = True
max_retries = 5
retry_backoff_base = 2.0
MIN_THRESHOLD = 100


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
      dump 
      4KB (4096 bytes) ' ' 
      0 

    ✅ 2 5 
    """
    timeout = 30
    poll_interval = 0.1
    elapsed = 0
    THRESHOLD = 4096

    last_receive_time = start_time
    last_total_bytes = 0
    retry_count = 0

    if process_ref is None:
        process_ref = [None]

    while elapsed < timeout:
        if os.path.exists(dump_file):
            try:
                size = os.path.getsize(dump_file)
                if size > THRESHOLD:
                    arrival_time = time.time()
                    latency_ms = (arrival_time - start_time) * 1000.0

                    # CSV : start_time, arrival_time, latency_ms
                    with open(log_file, "w") as f:
                        f.write(f"{start_time},{arrival_time},{latency_ms:.2f}\n")
                    return

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

                backoff_time = retry_backoff_base ** retry_count
                time.sleep(backoff_time)

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
                    "--url", retry_sub_url,
                    "--broadcast", retry_broadcast_name,
                    "--track", track_name,  # track
                    "--dump", dump_file,  # dump
                    "--tls-disable-verify"
                ]

                try:
                    # DataDrainer
                    retry_log_file = open(pub_log_file, "ab")
                    process_ref[0] = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,  # stderr stdout
                        bufsize=0
                    )

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

                    last_receive_time = time.time()
                except Exception as e:
                    try:
                        with open(pub_log_file, "a", errors="ignore") as f:
                            f.write(f"\n[RETRY ERROR] Failed to re-subscribe: {str(e)}\n")
                    except:
                        pass

        time.sleep(poll_interval)
        elapsed += poll_interval

def main():
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

    # broadcast
    broadcast_name = None
    if len(sys.argv) > 8:
        broadcast_name = sys.argv[8]

    if not url.startswith("http"):
        url = "https://" + url

    sub_url, broadcast_name = canonical_subscriber_url(url, broadcast_name)

    # dump <DUMP> ( )
    # tls-disable-verify ( TLS )
    cmd = [
        binary,
        "--url", sub_url,
        "--broadcast", broadcast_name,
        "--track", track_name,  # track
        "--dump", output_file,  # dump
        "--tls-disable-verify"
    ]

    process_ref = [None]
    log_file_handle = None
    try:
        log_file_handle = open(pub_log_file, "ab")  # append; never truncate scientific gst logs

        # PIPE moq-sub
        process_ref[0] = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # stderr stdout
            bufsize=0
        )

        def tee_output():
            """ sys.stdout """
            try:
                while True:
                    data = process_ref[0].stdout.read(4096)
                    if not data:
                        if process_ref[0].poll() is not None:
                            break
                        time.sleep(0.01)
                        continue
                    log_file_handle.write(data)
                    log_file_handle.flush()
                    sys.stdout.buffer.write(data)
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

    except Exception as e:
        if log_file_handle:
            log_file_handle.close()
        try:
            with open(pub_log_file, "a") as f:
                f.write(f"\n[FATAL] Failed to start process: {str(e)}\n")
        except:
            pass
        return

    # broadcast_name
    monitor_thread = threading.Thread(
        target=monitor_dump_file,
        args=(output_file, latency_log, start_time_arg, process_ref, binary, track_name, sub_url, pub_log_file, broadcast_name)
    )
    monitor_thread.daemon = True
    monitor_thread.start()

    monitor_thread.join(timeout=35)

    if process_ref[0] is not None:
        try:
            process_ref[0].wait()
        except:
            pass

if __name__ == "__main__":
    main()
