
import sys
sys.stderr.write("SCRIPT STARTED
")
sys.stdout.write("STDOUT WORKS
")
with open("/tmp/test_confirm.txt", "w") as g:
    g.write("FILE WRITE WORKS
")
sys.stderr.write("SCRIPT DONE
")
