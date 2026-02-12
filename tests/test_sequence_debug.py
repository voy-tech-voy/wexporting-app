from client.utils.sequence_detector import SequenceDetector

# Test with user's exact pattern: "gradient002.png with numbering 0001-0010"
# Interpretation: gradient002.png, gradient003.png, ..., gradient010.png

test_files = [
    "V:/test/gradient002.png",
    "V:/test/gradient003.png",
    "V:/test/gradient004.png",
    "V:/test/gradient005.png",
    "V:/test/gradient006.png",
    "V:/test/gradient007.png",
    "V:/test/gradient008.png",
    "V:/test/gradient009.png",
    "V:/test/gradient010.png",
]

print("Testing with gradient002.png - gradient010.png")
print(f"Total files: {len(test_files)}")
print()

sequences, singles = SequenceDetector.detect(test_files)

print(f"Sequences found: {len(sequences)}")
for seq in sequences:
    print(f"  - {seq['name']} ({seq['count']} files)")
    print(f"    Range: {seq['range']}")
    print(f"    Files: {seq['files'][:3]}..." if len(seq['files']) > 3 else f"    Files: {seq['files']}")

print(f"\nSingles found: {len(singles)}")
for s in singles[:5]:
    print(f"  - {s}")

# Test minimum requirement
print("\n" + "="*50)
print("Testing with only 2 files (minimum for sequence)")
test_2 = [
    "V:/test/gradient002.png",
    "V:/test/gradient003.png",
]
sequences, singles = SequenceDetector.detect(test_2)
print(f"Sequences: {len(sequences)}, Singles: {len(singles)}")
if sequences:
    print(f"  Sequence: {sequences[0]['name']}")
