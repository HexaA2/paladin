
import json


input_file = "C:/Users/Sri Vatsa/Desktop/FaiL-Safe Benchmark/ToolBench/data/newpaladinfull.jsonl"
cnt=0
cntx=0
cnty=0

with open(input_file, "r", encoding="utf-8") as infile:
    for line in infile:
      cntx=0
      obj = json.loads(line)
      convos = obj.get("conversations", [])
      for idx, message in enumerate(convos):
            value = message.get("value", "")
            if message.get("from", "") == "function" and "error" in value:
               cnt+=1
               cntx=1
               break
      if cntx==0:
          cnty+=1


print("error number:",cnt)
print("happy number:",cnty)