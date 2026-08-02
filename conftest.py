# Membuat paket `monitor` bisa diimpor saat pytest berjalan dari akar repo.
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
