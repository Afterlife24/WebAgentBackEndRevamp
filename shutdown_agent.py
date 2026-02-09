#!/usr/bin/env python3
"""
Script to properly shutdown the agent and server processes
"""
import os
import signal
import subprocess
import sys
import time
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_processes_by_name(process_name):
    """Find processes by name"""
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(['tasklist', '/FI', f'IMAGENAME eq {process_name}', '/FO', 'CSV'], 
                                  capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            processes = []
            for line in lines:
                if line.strip():
                    parts = line.split(',')
                    if len(parts) >= 2:
                        pid = parts[1].strip('"')
                        processes.append(pid)
            return processes
        else:  # Unix-like
            result = subprocess.run(['pgrep', '-f', process_name], capture_output=True, text=True)
            return result.stdout.strip().split('\n') if result.stdout.strip() else []
    except Exception as e:
        logger.error(f"Error finding processes: {e}")
        return []

def kill_process(pid):
    """Kill a process by PID"""
    try:
        if os.name == 'nt':  # Windows
            subprocess.run(['taskkill', '/PID', str(pid), '/F'], check=True)
        else:  # Unix-like
            os.kill(int(pid), signal.SIGTERM)
        logger.info(f"Killed process {pid}")
        return True
    except Exception as e:
        logger.error(f"Failed to kill process {pid}: {e}")
        return False

def shutdown_agent_and_server():
    """Shutdown agent and server processes"""
    logger.info("Starting shutdown process...")
    
    # Find Python processes that might be running our scripts
    python_processes = find_processes_by_name('python.exe' if os.name == 'nt' else 'python')
    logger.info(f"Found {len(python_processes)} Python processes")
    
    # Find processes using port 5001 (our server port)
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            port_processes = []
            for line in lines:
                if ':5001' in line and 'LISTENING' in line:
                    parts = line.split()
                    if len(parts) >= 5:
                        pid = parts[-1]
                        port_processes.append(pid)
        else:  # Unix-like
            result = subprocess.run(['lsof', '-ti:5001'], capture_output=True, text=True)
            port_processes = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        logger.info(f"Found {len(port_processes)} processes using port 5001")
        
        # Kill processes using port 5001
        for pid in port_processes:
            if pid.strip():
                logger.info(f"Killing process {pid} using port 5001")
                kill_process(pid.strip())
                
    except Exception as e:
        logger.error(f"Error checking port 5001: {e}")
    
    # Give processes time to shutdown gracefully
    time.sleep(2)
    
    # Check if any processes are still running
    remaining_processes = find_processes_by_name('python.exe' if os.name == 'nt' else 'python')
    if remaining_processes:
        logger.warning(f"Still {len(remaining_processes)} Python processes running")
        for pid in remaining_processes:
            logger.info(f"Force killing remaining process {pid}")
            kill_process(pid)
    
    logger.info("Shutdown process completed")

if __name__ == "__main__":
    shutdown_agent_and_server()
