from flask import Flask
import threading
import time

app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running", 200

def run_health_check():
    app.run(host='0.0.0.0', port=8000)

if __name__ == '__main__':
    # Health check server alag thread mein run karein
    health_thread = threading.Thread(target=run_health_check, daemon=True)
    health_thread.start()
    
    # Yahan aapka main bot code
    print("Health check server started on port 8000")
    
    # Keep running
    while True:
        time.sleep(1)
