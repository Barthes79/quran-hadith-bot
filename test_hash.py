import hashlib

# Test the topic hash function from the codebase
def topic_hash(topic_name: str) -> str:
    return hashlib.md5(topic_name.encode('utf-8')).hexdigest()[:12]

# Test with various topic names
test_topics = ['اخلاق', 'حدیث', 'patience', 'test', 'content']

print('Testing topic_hash function:')
for topic in test_topics:
    try:
        result = topic_hash(topic)
        print(f'  {topic}: {result}')
    except Exception as e:
        print(f'  {topic}: ERROR - {e}')