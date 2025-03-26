parts = ["out", "put", "!"]
trace on
variable = ""
for part in parts:
    variable += part
echo Some @(variable)