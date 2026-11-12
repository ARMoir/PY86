import gc
class Holder:
    def __init__(self, value):
        self.value = value
keepers = [Holder([i, str(i)]) for i in range(20)]
for n in range(100):
    garbage = [str(i) + 'x' for i in range(30)]
    gc.collect()
    for i in range(20):
        assert keepers[i].value == [i, str(i)]
print('PASS gc_roots')
