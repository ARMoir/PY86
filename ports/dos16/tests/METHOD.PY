s = 'caf\u00e9 \U0001f600'
b = s.encode('utf-8')
print(b)
print(b.decode('utf-8') == s)
print('PASS methods')
