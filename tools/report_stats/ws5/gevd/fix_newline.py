p = r"D:\signal_project\tools\report_stats\ws5\gevd\model\brain.c"
s = open(p, encoding="utf-8").read()
bad = 'fprintf(stderr, "WS5GEVD %.9e %.9e %.9e\n", na / nb'
assert s.count(bad) == 1
s = s.replace(bad, 'fprintf(stderr, "WS5GEVD %.9e %.9e %.9e\\n", na / nb')
open(p, "w", encoding="utf-8", newline="").write(s)
print("fixed")
