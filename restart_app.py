# restart app script
import os
import sys
import subprocess

def main(argv):
    # use the passed in argument to determine the app to restart
    if len(argv) < 3:
        print("Usage: restart_app.py <pid> <script_name>")
        sys.exit(1)
    pid = argv[1]
    script_name = argv[2]
    print(f"Restarting {script_name} with pid: " + pid)
    python = sys.executable
    # kill the app
    if os.name == 'nt':
        os.system(f'taskkill /F /PID {pid}')
    else:
        # check if jarvischatbot.service is running. use systemctl to get status and restart the service
        is_running = os.system(f'systemctl status jarvischatbot.service')
        if is_running == 0:
            os.system(f'systemctl restart jarvischatbot.service')
        else:
            os.kill(pid, signal.SIGTERM)
            # start the app
            subprocess.Popen([python, script_name])
    # start the app
    subprocess.Popen([python , script_name])

if __name__ == "__main__":
    main(sys.argv)