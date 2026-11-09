/* v5 platform register map (bare metal, no BSP). Addresses from build_v5.tcl assign_bd_address. */
#ifndef PLATFORM_H
#define PLATFORM_H
#include <stdint.h>
#define SYS_CLK_HZ   73728000u
#define UART_BAUD    921600u
#define GPIO_BASE    0x40000000u
#define UART_BASE    0x44A00000u
#define TIMER_BASE   0x41C00000u
#define REG(a)       (*(volatile uint32_t *)(a))
#endif
