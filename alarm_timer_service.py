# alarm_timer_service.py
import os
import platform
import subprocess
from datetime import datetime, timedelta
import tempfile

script_dir = os.path.dirname(os.path.abspath(__file__))
trigger_script_path = os.path.join(script_dir, "trigger_alarm_timer.py")
class AlarmTimerService:
    def __init__(self):
        self.cron_file = "/etc/cron.d/alarm_timer_cron"
        self.is_windows = platform.system() == "Windows"
        self.python_exe = "venv/bin/python3" if not self.is_windows else "venv/Scripts/python"
        
    def add_alarm(self, alarm_time, callback):
        print(f"Setting alarm for {alarm_time}.")
        cron_time = alarm_time.strftime('%M %H %d %m *')
        if self.is_windows:
            self._add_scheduled_task(alarm_time, "JarvisChatBotAlarmTask", "alarm")
        else:
            cron_command = os.path.join(script_dir, f"{self.python_exe} {trigger_script_path} alarm")
            self._add_cron_job(cron_time, cron_command)

    def add_timer(self, duration, callback):
        print(f"Setting timer for {duration} seconds.")
        timer_time = datetime.now() + timedelta(seconds=duration)
        cron_time = timer_time.strftime('%M %H %d %m *')
        if self.is_windows:
            self._add_scheduled_task(timer_time, "JarvisChatBotTimerTask", "timer")
        else:
            cron_command = os.path.join(script_dir, f"{self.python_exe} {trigger_script_path} timer")
            self._add_cron_job(cron_time, cron_command)

    def _add_cron_job(self, cron_time, cron_command):
        with open(self.cron_file, 'a') as cron_file:
            cron_file.write(f"{cron_time} {cron_command}\n")
        cron_command = f'"{cron_command}"'
        full_command = ["crontab", self.cron_file]
        print("Running alarm/timer command: " + " ".join(full_command))
        subprocess.run(full_command)

    def _add_scheduled_task(self, run_time, task_name, type):
        today = datetime.now()
        run_time_str = run_time.strftime('%H:%M:%S')
        date_str = run_time.strftime('%Y-%m-%d')
        theDate = today.strftime('%Y-%m-%d')+"T"+today.strftime('%H:%M:%S')
        # use the scheduled_task.xml template to create the task so we can set the seconds position
        with open(os.path.join(script_dir, "scheduled_task.xml"), "r", encoding="utf-16") as file:
            scheduled_task_xml = file.read()
        scheduled_task_xml = scheduled_task_xml.replace("{{{URI}}}", task_name)
        scheduled_task_xml = scheduled_task_xml.replace("{{{Command}}}", '"{}"'.format(os.path.join(script_dir,self.python_exe)))
        scheduled_task_xml = scheduled_task_xml.replace("{{{Arguments}}}", '"{}" {}'.format(os.path.join(script_dir,trigger_script_path), type))
        scheduled_task_xml = scheduled_task_xml.replace("{{{StartBoundary}}}", date_str+"T"+run_time_str)
        scheduled_task_xml = scheduled_task_xml.replace("{{{Date}}}", theDate)
        with tempfile.NamedTemporaryFile(suffix=".xml", mode='w', encoding='utf-16') as f:
            f.write(scheduled_task_xml)
            tempFile = f.name      
            full_command = ["schtasks", "/create", "/xml", tempFile, "/tn", task_name, "/f"]
            print("Running alarm/timer command: " + " ".join(full_command))
            subprocess.run(full_command)

    def delete_all_jobs(self):
        if self.is_windows:
            self._delete_all_scheduled_tasks()
        else:
            self._delete_all_cron_jobs()

    def _delete_all_cron_jobs(self):
        if os.path.exists(self.cron_file):
            os.remove(self.cron_file)
        subprocess.run(["crontab", "-r"])

    def _delete_all_scheduled_tasks(self):
        command = ["schtasks", "/delete", "/tn", "JarvisChatBotAlarmTask", "/f"]
        print(f"Deleting all JarvisChatBotAlarmTask scheduled tasks...{' '.join(command)}")
        subprocess.run(command)
        command = ["schtasks", "/delete", "/tn", "JarvisChatBotTimerTask", "/f"]
        print(f"Deleting all JarvisChatBotTimerTask scheduled tasks...{' '.join(command)}")
        subprocess.run(command)
        print("Tasks deleted.")