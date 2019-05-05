# Run the separate processes in the background
python3 Processes/Tracker/run_tracker.py &
python3 Features/TemplateRequestFeature/Processes/InboxListener/run_inbox_listener.py &
python3 Features/TemplateRequestFeature/Processes/TemplateRequestListener/run_request_listener.py &

# Run the main loop
python3 main.py
