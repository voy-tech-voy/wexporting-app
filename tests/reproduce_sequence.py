from client.utils.sequence_detector import SequenceDetector
import os

# Test cases based on "gradient002.png with numbering 0001-0010"
# Interpretation 1: Base is "gradient002", sequence is 0001-0010 appended
files_1 = [
    "V:/test/gradient002_0001.png",
    "V:/test/gradient002_0002.png",
    "V:/test/gradient002_0003.png",
    "V:/test/gradient002_0010.png"
]

# Interpretation 2: Base is "gradient", sequence is 001-010 (and 002 is one of them)
files_2 = [
    "V:/test/gradient001.png",
    "V:/test/gradient002.png",
    "V:/test/gradient003.png",
    "V:/test/gradient010.png"
]

# Interpretation 3: Base is "gradient002.", sequence is 0001-0010
files_3 = [
    "V:/test/gradient002.0001.png",
    "V:/test/gradient002.0002.png"
]

print("--- Test Case 1: gradient002_0001.png ---")
seqs, singles = SequenceDetector.detect(files_1)
for s in seqs:
    print(f"Sequence: {s['name']} (Count: {s['count']})")
if singles:
    print(f"Singles: {singles}")

print("\n--- Test Case 2: gradient002.png (as part of gradient###) ---")
seqs, singles = SequenceDetector.detect(files_2)
for s in seqs:
    print(f"Sequence: {s['name']} (Count: {s['count']})")
if singles:
    print(f"Singles: {singles}")
    
print("\n--- Test Case 3: gradient002.0001.png ---")
seqs, singles = SequenceDetector.detect(files_3)
for s in seqs:
    print(f"Sequence: {s['name']} (Count: {s['count']})")
if singles:
    print(f"Singles: {singles}")
