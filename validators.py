import re

def valid_phone(phone):
    return re.fullmatch(r"05\d{8}", phone)

def valid_name(name):
    return len(name.strip().split()) >= 3
