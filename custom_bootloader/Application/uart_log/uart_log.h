/*
 * uart_log.h
 *
 *  Created on: May 12, 2025
 *      Author: RyanDank
 */

#ifndef UART_LOG_UART_LOG_H_
#define UART_LOG_UART_LOG_H_

#include "main.h"
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <stdint.h>
#include "uart_command.h"
#define BL_DEBUG_MSG_EN
void printmsg(char *format,...);
#endif /* UART_LOG_UART_LOG_H_ */
