"""
Task scheduler for periodic jobs like sending daily reports.
"""
import threading
import schedule
import time
import logging
from datetime import datetime, timedelta
import pytz
from typing import Dict, Any, Callable, Optional

class TaskScheduler:
    """
    Handles scheduling of periodic tasks.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.scheduler_thread = None
        
        # Timezone for South Africa Time (SAT)
        self.sat_timezone = pytz.timezone('Africa/Johannesburg')
        
    def start(self):
        """Start the scheduler thread."""
        if self.running:
            self.logger.warning("Scheduler is already running")
            return
            
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        self.logger.info("Scheduler started")
        
    def stop(self):
        """Stop the scheduler thread."""
        if not self.running:
            return
            
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=1.0)
        schedule.clear()
        self.logger.info("Scheduler stopped")
        
    def _run_scheduler(self):
        """Run the scheduler loop."""
        while self.running:
            schedule.run_pending()
            time.sleep(1)
            
    def schedule_daily_task(self, task_func: Callable, time_str: str, *args, **kwargs):
        """
        Schedule a task to run daily at the specified time (SAT timezone).
        
        Args:
            task_func: Function to execute
            time_str: Time string in "HH:MM" format (24-hour)
            *args, **kwargs: Arguments to pass to the task function
        """
        # Schedule the task
        schedule.every().day.at(time_str).do(self._run_task_with_timezone, task_func, *args, **kwargs)
        
        # Calculate time until next run
        now = datetime.now(self.sat_timezone)
        time_parts = time_str.split(":")
        scheduled_hour, scheduled_minute = int(time_parts[0]), int(time_parts[1])
        
        scheduled_time = now.replace(hour=scheduled_hour, minute=scheduled_minute, second=0, microsecond=0)
        
        # If the scheduled time is in the past, add one day
        if scheduled_time < now:
            scheduled_time += timedelta(days=1)
            
        # Calculate the time difference
        time_diff = scheduled_time - now
        
        # Log the next scheduled run
        self.logger.info(f"Task scheduled to run daily at {time_str} SAT (next run in {time_diff})")
        
    def _run_task_with_timezone(self, task_func: Callable, *args, **kwargs):
        """
        Run a task with the correct timezone context.
        
        Args:
            task_func: Function to execute
            *args, **kwargs: Arguments to pass to the task function
        """
        try:
            # Create a timezone aware datetime for the current time in SAT
            now = datetime.now(self.sat_timezone)
            
            # Add the current time to the kwargs
            kwargs['current_time'] = now
            
            # Execute the task
            self.logger.info(f"Running scheduled task: {task_func.__name__}")
            return task_func(*args, **kwargs)
            
        except Exception as e:
            self.logger.error(f"Error executing scheduled task: {e}")
            return False

# Initialize task scheduler
task_scheduler = TaskScheduler()
