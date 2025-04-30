from datetime import datetime, timedelta
from xmlrpc.client import DateTime



time_format = "%Y-%m-%dT%H:%M:%S.%fZ"  # Example: "2023-10-01T12:00:00.000Z"
time_format_no_ms = "%Y-%m-%dT%H:%M:%S"  # Example: "2023-10-01T12:00:00"   

print(datetime.now().fromisoformat(time_format)) # Example: "2023-10-01T12:00:00.000Z"    