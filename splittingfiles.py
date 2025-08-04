input_file = "C:/Users/Sri Vatsa/Desktop/FaiL-Safe Benchmark/ToolBench/data/newpaladinfull.jsonl"
output_file = "C:/Users/Sri Vatsa/Desktop/FaiL-Safe Benchmark/ToolBench/data/27-30k.jsonl"

import json

cnt=0
var=3000 #Size of Chunks
multi=9 #Multiplier to set the ranges

with open(input_file, "r", encoding="utf-8") as infile, open(output_file, "w", encoding="utf-8") as outfile:
    for line in infile:
      cnt+=1
      if cnt>(var*multi) and cnt<=((var*multi)+3000): #Add one chunk size
        obj = json.loads(line)
        outfile.write(json.dumps(obj, ensure_ascii=False) + "\n")
      if cnt==((var*multi)+3001): #add one above one chunk size 
            break
        

            