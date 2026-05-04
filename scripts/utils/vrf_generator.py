import binascii
from urllib.parse import quote

class VRFGenerator:
    def __init__(self, keyword: str):
        self.keyword = keyword
        self.key_l = "FgxyJUQDPUGSzwbAq/ToWn4/e8jYzvabE+dLMb1XU1o="
        self.key_g = "CQx3CLwswJAnM1VxOqX+y+f3eUns03ulxv8Z+0gUyik="
        self.key_B = "fAS+otFLkKsKAJzu3yU+rGOlbbFVq+u+LaS6+s1eCJs="
        self.key_m = "Oy45fQVK9kq9019+VysXVlz1F9S1YwYKgXyzGlZrijo="
        self.key_F = "aoDIdXezm2l3HrcnQdkPJTDT8+W6mcl2/02ewBHfPzg="

        self.seed_A = "yH6MXnMEcDVWO/9a6P9W92BAh1eRLVFxFlWTHUqQ474="
        self.seed_V = "RK7y4dZ0azs9Uqz+bbFB46Bx2K9EHg74ndxknY9uknA="
        self.seed_N = "rqr9HeTQOg8TlFiIGZpJaxcvAaKHwMwrkqojJCpcvoc="
        self.seed_P = "/4GPpmZXYpn5RpkP7FC/dt8SXz7W30nUZTe8wb+3xmU="
        self.seed_k = "wsSGSBXKWA9q1oDJpjtJddVxH+evCfL5SO9HZnUDFU8="

        self.prefix_O = "l9PavRg="
        self.prefix_v = "Ml2v7ag1Jg=="
        self.prefix_L = "i/Va0UxrbMo="
        self.prefix_p = "WFjKAHGEkQM="
        self.prefix_W = "5Rr27rWd"

        self.schedule_c = (
            self.sub8(223), self.rotr8(4), self.rotr8(4), self.add8(234), self.rotr8(7),
            self.rotr8(2), self.rotr8(7), self.sub8(223), self.rotr8(7), self.rotr8(6),
        )
        self.schedule_y = (
            self.add8(19), self.rotr8(7), self.add8(19), self.rotr8(6), self.add8(19),
            self.rotr8(1), self.add8(19), self.rotr8(6), self.rotr8(7), self.rotr8(4),
        )
        self.schedule_b = (
            self.sub8(223), self.rotr8(1), self.add8(19), self.sub8(223), self.rotl8(2),
            self.sub8(223), self.add8(19), self.rotl8(1), self.rotl8(2), self.rotl8(1),
        )
        self.schedule_j = (
            self.add8(19), self.rotl8(1), self.rotl8(1), self.rotr8(1), self.add8(234),
            self.rotl8(1), self.sub8(223), self.rotl8(6), self.rotl8(4), self.rotl8(1),
        )
        self.schedule_e = (
            self.rotr8(1), self.rotl8(1), self.rotl8(6), self.rotr8(1), self.rotl8(2),
            self.rotr8(4), self.rotl8(1), self.rotl8(1), self.sub8(223), self.rotl8(2),
        )

        self.vrf_token = self.generate_VRF()
        self.search_url = f"https://mangafire.to/filter?keyword={quote(self.keyword)}&vrf={self.vrf_token}"
        
    def get_search_url(self) -> str:
        return self.search_url

    def transform(self, input, seed, prefix, schedule):
        prefix_len = len(prefix)

        out = []
        for idx, c in enumerate(input):
            if idx < prefix_len:
                out.append(prefix[idx] or 0)
            out.append(schedule[idx % 10]((c ^ seed[idx % 32]) & 255) & 255)
        return out

    def rc4(self, key, input):
        lkey = len(key)

        j = 0
        s = list(range(256))
        for i in range(256):
            j = (j + s[i] + key[i % lkey]) & 255
            s[i], s[j] = s[j], s[i]

        out = []
        i = j = 0
        for c in input:
            i = (i + 1) & 255
            j = (j + s[i]) & 255
            s[i], s[j] = s[j], s[i]
            k = s[(s[i] + s[j]) & 255]
            out.append(c ^ k)
        return out

    def add8(self, n): return lambda c: (c + n) & 255

    def sub8(self, n): return lambda c: (c - n + 256) & 255

    def xor8(self, n): return lambda c: (c ^ n) & 255

    def rotl8(self, n): return lambda c: ((c << n) | (c >> (8 - n))) & 255

    def rotr8(self, n): return lambda c: ((c >> n) | (c << (8 - n))) & 255

    def generate_VRF(self):
        input = quote(self.keyword).encode()
        
        for key_b64, seed_b64, prefix_b64, schedule in (
            (self.key_l, self.seed_A, self.prefix_O, self.schedule_c),
            (self.key_g, self.seed_V, self.prefix_v, self.schedule_y),
            (self.key_B, self.seed_N, self.prefix_L, self.schedule_b),
            (self.key_m, self.seed_P, self.prefix_p, self.schedule_j),
            (self.key_F, self.seed_k, self.prefix_W, self.schedule_e),
        ):
            input = self.transform(
                self.rc4(binascii.a2b_base64(key_b64), input),
                binascii.a2b_base64(seed_b64),
                binascii.a2b_base64(prefix_b64),
                schedule,
            )
        
        return binascii.b2a_base64(bytes(input), newline=False).rstrip(
            b"=").replace(b"+", b"-").replace(b"/", b"_").decode()
 