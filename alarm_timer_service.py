# alarm_timer_service.py
import os
import platform
import subprocess
from datetime import datetime, timedelta
import tempfile

SYSTEMD_PATH = '/etc/systemd/system'
script_dir = os.path.dirname(os.path.abspath(__file__))
trigger_script_path = os.path.join(script_dir, "trigger_alarm_timer.py")
class AlarmTimerService:
    def __init__(self):
        is_windows = platform.system() == "Windows"
        self.cron_file = "/etc/cron.d/alarm_timer_cron"
        self.is_windows = is_windows
        self.python_exe = os.path.join(script_dir, "venv/bin/python3" if not self.is_windows else "venv/Scripts/python")
        self.buffer_time = 0
        self._create_systemd_unit_file('jarvis_alarm.service', self._generate_systemd_service('alarm'), is_alarm=True)
        self._create_systemd_unit_file('jarvis_timer.service', self._generate_systemd_service('timer'), is_alarm=False)
        self._create_systemd_unit_file('jarvis_alarm.timer', self._generate_systemd_timer(datetime.now(), 'jarvis_alarm.service', is_alarm=True), is_alarm=True)
        self._create_systemd_unit_file('jarvis_timer.timer', self._generate_systemd_timer(0, 'jarvis_timer.service', is_alarm=False), is_alarm=False)
        for timer_name in ["jarvis_alarm.timer", "jarvis_timer.timer"]:
            self._reload_timer(timer_name)
        
    def add_alarm(self, alarm_time, callback):
        print(f"Setting alarm for {alarm_time}.")
        service_name = 'jarvis_alarm.service'
        timer_name = 'jarvis_alarm.timer'
        if self.is_windows:
            self._add_scheduled_task(alarm_time, "JarvisChatBotAlarmTask", "alarm")
        else:
            self._edit_systemd_unit_file(timer_name, self._generate_systemd_timer(alarm_time, service_name, is_alarm=True))
            self._start_timer(timer_name)

    def add_timer(self, duration, callback):
        print(f"Setting timer for {duration} seconds.")
        service_name = 'jarvis_timer.service'
        timer_name = 'jarvis_timer.timer'
        # Add self.buffer_time seconds to the duration to account for the time it takes to start the timer
        timer_time = datetime.now() + timedelta(seconds=duration + self.buffer_time)
        if self.is_windows:
            self._add_scheduled_task(timer_time, "JarvisChatBotTimerTask", "timer")
        else:
            self._edit_systemd_unit_file(timer_name, self._generate_systemd_timer(duration, service_name, is_alarm=False))
            self._start_timer(timer_name)

    def _add_scheduled_task(self, run_time, task_name, type):
        today = datetime.now()
        run_time_str = run_time.strftime('%H:%M:%S')
        date_str = run_time.strftime('%Y-%m-%d')
        theDate = today.strftime('%Y-%m-%d')+"T"+today.strftime('%H:%M:%S')
        # use the scheduled_task.xml template to create the task so we can set the seconds position
        with open(os.path.join(script_dir, "scheduled_task.xml"), "r", encoding="utf-16") as file:
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
            print("Running alarm/timer command: " + " ".join(full_command))
            subprocess.run(full_command)

    def delete_all_jobs(self):
        if self.is_windows:
            self._delete_all_scheduled_tasks()
        else:
            self.clear_systemd_timers()

    def _delete_all_scheduled_tasks(self):
        command = ["schtasks", "/delete", "/tn", "JarvisChatBotAlarmTask", "/f"]
        print(f"Deleting all JarvisChatBotAlarmTask scheduled tasks...{' '.join(command)}")
        subprocess.run(command)
        command = ["schtasks", "/delete", "/tn", "JarvisChatBotTimerTask", "/f"]
        print(f"Deleting all JarvisChatBotTimerTask scheduled tasks...{' '.join(command)}")
        subprocess.run(command)
        print("Tasks deleted.")
    
    def _generate_systemd_service(self, task_type):
        service_content = f"""
        [Unit]
        Description=Jarvis {task_type.capitalize()} Service

        [Service]
        ExecStart={self.python_exe} {trigger_script_path} {task_type}
        """
        return service_content

    def _generate_systemd_timer(self, time_value, service_name, is_alarm=False):
        if is_alarm:
            # Alarms should repeat at the same time every day
            on_calendar = time_value.strftime('*-*-* %H:%M:%S')
        else:
            # Timers should not repeat
            time_value = datetime.now() + time_value
            on_calendar = time_value.strftime('%Y-%m-%d %H:%M:%S')
        
        timer_content = f"""
        [Unit]
        Description=Run Jarvis {service_name.split('_')[1].capitalize()} Timer

        [Timer]
        AccuracySec=1s
        OnCalendar={on_calendar}
        Persistent=true

        [Install]
        WantedBy=timers.target
        """
        return timer_content
    
    def _create_systemd_unit_file(self, name, content, is_alarm=False):
        path = os.path.join(SYSTEMD_PATH, name)
        with open(path, 'w') as timer_file:
            timer_file.write(content)
        print("Created " + ("alarm" if is_alarm else "timer") + f" file at {path}")

    def _edit_systemd_unit_file(self, name, content):
        # Use systemctl edit to create or modify the timer
        os.system(f'echo "{content}" | sudo systemctl edit --full {name}')
        print(f"Timer {name} created/modified using systemctl edit")

    def _reload_and_start_timer(self, timer_name):
        self._reload_timer(timer_name)
        self._start_timer(timer_name)
    
    def _reload_timer(self, timer_name):
        os.system(f'sudo systemctl daemon-reload --now')
        print(f"Enabled {timer_name}")

    def _start_timer(self, timer_name):
        os.system(f'sudo systemctl enable --now {timer_name}')
        os.system(f'sudo systemctl try-reload-or-restart --now {timer_name}')
        print(f"Started {timer_name}")
    
    def clear_systemd_timers(self):
        timer_names = ["jarvis_alarm.timer", "jarvis_timer.timer"]
        # service_names = ["jarvis_alarm.service", "jarvis_timer.service"]
        
        for timer_name in timer_names:
            print(f"Stopping and disabling {timer_name}...")
            os.system(f'sudo systemctl stop {timer_name}')
            os.system(f'sudo systemctl disable {timer_name}')
        
        # for timer_name, service_name in zip(timer_names, service_names):
        #     timer_path = os.path.join(SYSTEMD_PATH, timer_name)
        #     service_path = os.path.join(SYSTEMD_PATH, service_name)
            
        #     if os.path.exists(timer_path):
        #         print(f"Deleting {timer_path}...")
        #         os.remove(timer_path)
            
        #     if os.path.exists(service_path):
        #         print(f"Deleting {service_path}...")
        #         os.remove(service_path)
        
        #os.system('sudo systemctl daemon-reload')
        print("Cleared all systemd timers and services.")