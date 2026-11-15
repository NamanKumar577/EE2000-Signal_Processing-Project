p = r"D:\signal_project\tools\report_stats\ws5\gevd\model\brain.c"
s = open(p, encoding="utf-8").read()
a = "    for (int i = 3; i >= 0; i--) {\n        double s = u[i];\n        for (int k = i + 1; k < 4; k++) s -= L[k * 4 + i] * w[k];\n        w[i] = s / L[i * 4 + i];\n    }\n    return 1;\n}"
assert s.count(a) == 1
b = a.replace("    return 1;\n}", """#ifdef WS5_LOG
    { double na = 0.0, nb = 0.0;                       /* logging only: Rayleigh quotient of the returned w */
      for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) { na += w[i] * A[i * 4 + j] * w[j]; nb += w[i] * Bm[i * 4 + j] * w[j]; }
      fprintf(stderr, "WS5GEVD %.9e %.9e %.9e\n", na / nb, ev[3], ev[0]); }
#endif
    return 1;
}""")
s = s.replace(a, b)
open(p, "w", encoding="utf-8", newline="").write(s)
print("patched")
