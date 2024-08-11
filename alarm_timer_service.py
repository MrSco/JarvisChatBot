# alarm_timer_service.py
import os
import platform
import subprocess
from datetime import datetime, timedelta
import tempfile
import threading

script_dir = os.path.dirname(os.path.abspath(__file__))
trigger_script_path = os.path.join(script_dir, "trigger_alarm_timer.py")
dynamic_timer_script_path = os.path.join(script_dir, 'dynamic_timer.sh')
scheduled_task_xml_path = os.path.join(script_dir, "scheduled_task.xml")
is_windows = platform.system() == "Windows"

class AlarmTimerService:
    def __init__(self):
        self.alarm_cron_file = "/etc/cron.d/alarm_cron"
        self.timer_cron_file = "/etc/cron.d/timer_cron"
        self.alarm_task_name = "JarvisChatBotAlarmTask"
        self.timer_task_name = "JarvisChatBotTimerTask"
        self.python_exe = os.path.join(script_dir, "venv/bin/python3" if not is_windows else "venv/Scripts/python")
        self.timer_thread = None
        self.cancel_event = threading.Event()
        
    def add_alarm(self, alarm_time):
        print(f"Setting alarm for {alarm_time}.")
        if is_windows:
            self._add_scheduled_task(alarm_time, self.alarm_task_name, "alarm")
        else:
            self._add_cron_job(alarm_time, "alarm")

    def add_timer(self, duration):
        print(f"Setting timer for {duration} seconds.")
        timer_time = datetime.now() + timedelta(seconds=duration)
        if is_windows:
            self._add_scheduled_task(timer_time, self.timer_task_name, "timer")
        else:
            self._add_cron_job(timer_time, "timer")

    def _add_cron_job(self, time_value, job_type):
        current_crontab = ""
        cron_file = self.alarm_cron_file if job_type == "alarm" else self.timer_cron_file
        # Determine the command to run
        cron_time = f"{time_value.strftime('%M %H')} * * *" 
        command = f"{self.python_exe} {trigger_script_path} {job_type}"
        if job_type == "timer":
            current_time = datetime.now()
            delay = (time_value - current_time).total_seconds()
            if delay < 60:
                self.cleanup()
                self.timer_thread = threading.Thread(target=self._run_command_after_delay, args=(delay, job_type))
                self.timer_thread.start()
                return
            else:
            # check if the time_value seconds is 0.
                if time_value.second != 0:
                    command = f"{dynamic_timer_script_path} {time_value.second} {job_type}"
                cron_time = f"{time_value.strftime('%M %H %d %m')} *"

        new_cron_job = f"{cron_time} {command}\n"

        # Read the current cron file
        if os.path.exists(cron_file):
            with open(cron_file, 'r') as file:
                current_crontab = file.read()      

        # Add the new cron job to the cron file
        updated_crontab = current_crontab + new_cron_job

        # Write the updated cron file
        with open(cron_file, 'w') as file:
            file.write(updated_crontab)

        # Apply the updated cron file
        subprocess.run(['crontab', cron_file])

        print(f"{job_type.capitalize()} set for {time_value}")

    def _run_command_after_delay(self, delay, job_type):
        if not self.cancel_event.wait(delay):
            command = f"{self.python_exe} {trigger_script_path} {job_type}"
            subprocess.run(command, shell=True)

    def _add_scheduled_task(self, run_time, task_name, type):
        today = datetime.now()
        run_time_str = run_time.strftime('%H:%M:%S')
        date_str = run_time.strftime('%Y-%m-%d')
        theDate = today.strftime('%Y-%m-%d')+"T"+today.strftime('%H:%M:%S')
        # use the scheduled_task.xml template to create the task so we can set the seconds position
        with open(scheduled_task_xml_path, "r", encoding="utf-16") as file:
            scheduled_task_xml = file.read()
        scheduled_task_xml = scheduled_task_xml.replace("{{{URI}}}", task_name)
        scheduled_task_xml = scheduled_task_xml.replace("{{{Command}}}", '"{}"'.format(self.python_exe))
        scheduled_task_xml = scheduled_task_xml.replace("{{{Arguments}}}", '"{}" {}'.format(os.path.join(script_dir,trigger_script_path), type))
        scheduled_task_xml = scheduled_task_xml.replace("{{{StartBoundary}}}", date_str+"T"+run_time_str)
        scheduled_task_xml = scheduled_task_xml.replace("{{{Date}}}", theDate)
        with tempfile.NamedTemporaryFile(suffix=".xml", mode='w', encoding='utf-16') as f:
            f.write(scheduled_task_xml)
            tempFile = f.name      
            full_command = ["schtasks", "/create", "/xml", tempFile, "/tn", task_name, "/f"]
            print(f"Running {type} command: " + " ".join(full_command))
            subprocess.run(full_command)

    def cleanup(self):
        print("Cleaning up alarm_timer_service...")
        self.cancel_event.set()  # Signal any running thread to stop
        if self.timer_thread and self.timer_thread.is_alive():
            self.timer_thread.join()
        self.cancel_event.clear()

    def delete_all_jobs(self, job_type):
        if is_windows:
            self._delete_all_scheduled_tasks(self.alarm_task_name if job_type == "alarm" else self.timer_task_name)
        else:
            if job_type == "timer":
                self.cleanup()
            self._delete_all_cron_jobs(job_type)

    def _delete_all_scheduled_tasks(self, task_name):
        command = ["schtasks", "/delete", "/tn", task_name, "/f"]
        print(f"Deleting all {task_name} scheduled tasks...{' '.join(command)}")
        subprocess.run(command)
        print("Tasks deleted.")

    def _delete_all_cron_jobs(self, job_type):
        cron_file = self.alarm_cron_file if job_type == "alarm" else self.timer
        if os.path.exists(cron_file):
            os.remove(cron_file)
            subprocess.run(['crontab', cron_file])
            print(f"All {job_type} cron jobs deleted.")