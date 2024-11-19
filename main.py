import israelrailapi
from datetime import datetime

now = datetime.now()

current_time = now.strftime("%H:%M")


s = israelrailapi.TrainSchedule()
print(s.query('Lod', 'Kiryat Gat', start_hour="20:00"))




print("Current Time =", current_time)