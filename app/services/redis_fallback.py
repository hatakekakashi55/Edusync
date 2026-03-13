"""
EduSync Backend - Redis Fallback
In-memory Redis fallback for Windows/local development.
"""


class FakeRedis:
    """In-memory fallback when Redis is not available"""
    def __init__(self):
        self.storage = {}
    
    async def ping(self): return True
    
    async def get(self, key):
        return self.storage.get(key)
    
    async def set(self, key, value, ex=None):
        self.storage[key] = value
        return True
    
    async def setex(self, key, seconds, value):
        """Set key with expiration time (seconds parameter comes before value in Redis setex)"""
        self.storage[key] = value
        return True
    
    async def exists(self, key):
        return key in self.storage
        
    async def lpush(self, key, *values):
        if key not in self.storage: self.storage[key] = []
        for v in values:
            self.storage[key].insert(0, v)
        return len(self.storage[key])
        
    async def lrange(self, key, start, stop):
        if key not in self.storage: return []
        data = self.storage[key]
        if stop == -1: return data[start:]
        return data[start:stop+1]
        
    async def ltrim(self, key, start, stop):
        if key in self.storage:
            self.storage[key] = self.storage[key][start:stop+1]
        return True
        
    async def expire(self, key, seconds): return True
    
    async def delete(self, *keys):
        for k in keys:
            self.storage.pop(k, None)
        return True
