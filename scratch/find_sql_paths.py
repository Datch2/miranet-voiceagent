import re

with open("D:\\miranet-voiceagent\\cacti_full.sql", "r", encoding="utf-8") as f:
    for line in f:
        if "INSERT INTO `settings`" in line or "INSERT INTO settings" in line:
            matches = re.findall(r"\('([^']+)','([^']*)'\)", line)
            for name, value in matches:
                if "poller" in name:
                    print(f"Setting: {name} => {value}")
