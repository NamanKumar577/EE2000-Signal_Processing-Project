/* Minimal BSP replacement: newlib's console hooks (unused; firmware talks to the UART directly). */
char inbyte(void) { return 0; }
void outbyte(char c) { (void)c; }
