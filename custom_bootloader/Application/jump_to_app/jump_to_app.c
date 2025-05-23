/*
 * jump_to_app.c
 *
 *  Created on: May 13, 2025
 *      Author: RyanDank
 */


#include "jump_to_app.h"

#define TRIGGER_ADDR     ((uint8_t *)0x08007FFD)
#define STATUS_APP_EXIST ((uint8_t *)0x08007FFE)
#define LENGTH_APP	     ((uint32_t *)0x08007FF0)
#define APP_ADDR        0x08008000

#define SECTOR_1_BASE    0x08004000
#define SECTOR_1_NUMBER  1

static void jump_to_application(uint32_t app_address);

//void check_and_jump_boot_mode(void) {
//    // Kiểm tra trigger
//    if (*TRIGGER_ADDR != 0xBB)
//        return;
//
//    uint8_t status_app_exist = *STATUS_APP_EXIST;
//    uint32_t length_app = *LENGTH_APP;
//
//    // Mở khóa flash
//    if ((FLASH->CR & FLASH_CR_LOCK) != 0) {
//        FLASH->KEYR = 0x45670123;
//        FLASH->KEYR = 0xCDEF89AB;
//    }
//
//    // Đợi flash không busy
//    while (FLASH->SR & FLASH_SR_BSY);
//
//    // Xóa sector 1
//    FLASH->CR &= ~FLASH_CR_SNB;
//    FLASH->CR |= FLASH_CR_SER | (SECTOR_1_NUMBER << FLASH_CR_SNB_Pos);
//    FLASH->CR |= FLASH_CR_STRT;
//
//    // Đợi xóa xong
//    while (FLASH->SR & FLASH_SR_BSY);
//
//
//
//    // Tắt SER
//    FLASH->CR &= ~FLASH_CR_SER;
//
//    // Bật chế độ lập trình
//    FLASH->CR |= FLASH_CR_PG;
//    // Ghi byte
//    *(volatile uint8_t *)STATUS_APP_EXIST = status_app_exist;
//    // Đợi ghi xong
//    while (FLASH->SR & FLASH_SR_BSY);
//    // Tắt ghi
//    FLASH->CR &= ~FLASH_CR_PG;
//
//    // Bật chế độ lập trình
//    FLASH->CR |= FLASH_CR_PG;
//    // Ghi byte
//    FLASH->CR |= FLASH_CR_PG;
//    *(volatile uint32_t *)LENGTH_APP = length_app;
//    // Đợi ghi xong
//    while (FLASH->SR & FLASH_SR_BSY);
//    // Tắt ghi
//    FLASH->CR &= ~FLASH_CR_PG;
//
//    // Khóa lại Flash
//    FLASH->CR |= FLASH_CR_LOCK;
//
//    // Xử lý nhảy ứng dụng
//	SCB->VTOR = APP_ADDR;
//	jump_to_application(APP_ADDR);
//
//}

#include "stm32f4xx.h" // Đảm bảo include file tiêu đề đúng cho STM32F401

void check_and_jump_boot_mode(void) {
    // Kiểm tra trigger
    if (*TRIGGER_ADDR != 0xBB)
        return;

    uint8_t status_app_exist = *(volatile uint8_t *)STATUS_APP_EXIST;
    uint32_t length_app = *(volatile uint32_t *)LENGTH_APP;

        // Mở khóa flash
        if ((FLASH->CR & FLASH_CR_LOCK) != 0) {
            FLASH->KEYR = 0x45670123;
            FLASH->KEYR = 0xCDEF89AB;
        }

        // Đợi flash không busy
        while (FLASH->SR & FLASH_SR_BSY);

        // Xóa sector 1
        FLASH->CR &= ~FLASH_CR_SNB;
        FLASH->CR |= FLASH_CR_SER | (SECTOR_1_NUMBER << FLASH_CR_SNB_Pos);
        FLASH->CR |= FLASH_CR_STRT;

        // Đợi xóa xong
        while (FLASH->SR & FLASH_SR_BSY);

    // Kiểm tra lỗi xóa (dùng WRPERR thay vì ERSERR)
    if (FLASH->SR & (FLASH_SR_WRPERR | FLASH_SR_PGAERR | FLASH_SR_PGPERR | FLASH_SR_PGSERR)) {
        FLASH->SR = (FLASH_SR_WRPERR | FLASH_SR_PGAERR | FLASH_SR_PGPERR | FLASH_SR_PGSERR); // Xóa cờ lỗi
        FLASH->CR |= FLASH_CR_LOCK; // Khóa lại Flash
        return; // Thoát nếu xóa thất bại
    }

    // Tắt chế độ xóa
    FLASH->CR &= ~FLASH_CR_SER;

    // Ghi byte vào STATUS_APP_EXIST
    FLASH->CR &= ~(FLASH_CR_PSIZE); // Xóa PSIZE
    FLASH->CR |= (0x0 << FLASH_CR_PSIZE_Pos); // PSIZE = 0x0 cho byte (8-bit)
    FLASH->CR |= FLASH_CR_PG; // Bật chế độ lập trình
    *(volatile uint8_t *)STATUS_APP_EXIST = status_app_exist;
    while (FLASH->SR & FLASH_SR_BSY); // Đợi ghi xong

    // Kiểm tra lỗi ghi
    if (FLASH->SR & (FLASH_SR_WRPERR | FLASH_SR_PGAERR | FLASH_SR_PGPERR | FLASH_SR_PGSERR)) {
        FLASH->SR = (FLASH_SR_WRPERR | FLASH_SR_PGAERR | FLASH_SR_PGPERR | FLASH_SR_PGSERR); // Xóa cờ lỗi
        FLASH->CR &= ~FLASH_CR_PG; // Tắt chế độ lập trình
        FLASH->CR |= FLASH_CR_LOCK; // Khóa lại Flash
        return; // Thoát nếu ghi thất bại
    }
    FLASH->CR &= ~FLASH_CR_PG; // Tắt chế độ lập trình

    // Ghi word vào LENGTH_APP
    FLASH->CR &= ~(FLASH_CR_PSIZE); // Xóa PSIZE
    FLASH->CR |= (0x2 << FLASH_CR_PSIZE_Pos); // PSIZE = 0x2 cho word (32-bit)
    FLASH->CR |= FLASH_CR_PG; // Bật chế độ lập trình
    *(volatile uint32_t *)LENGTH_APP = length_app;
    while (FLASH->SR & FLASH_SR_BSY); // Đợi ghi xong

    // Kiểm tra lỗi ghi
    if (FLASH->SR & (FLASH_SR_WRPERR | FLASH_SR_PGAERR | FLASH_SR_PGPERR | FLASH_SR_PGSERR)) {
        FLASH->SR = (FLASH_SR_WRPERR | FLASH_SR_PGAERR | FLASH_SR_PGPERR | FLASH_SR_PGSERR); // Xóa cờ lỗi
        FLASH->CR &= ~FLASH_CR_PG; // Tắt chế độ lập trình
        FLASH->CR |= FLASH_CR_LOCK; // Khóa lại Flash
        return; // Thoát nếu ghi thất bại
    }
    FLASH->CR &= ~FLASH_CR_PG; // Tắt chế độ lập trình

    // Khóa lại Flash
    FLASH->CR |= FLASH_CR_LOCK;

    // Xử lý nhảy ứng dụng
    SCB->VTOR = APP_ADDR;
    jump_to_application(APP_ADDR);
}

static void jump_to_application(uint32_t app_address) {

    uint32_t jump_addr = *(__IO uint32_t *)(app_address + 4);
    void (*app_reset_handler)(void) = (void *)jump_addr;
    __set_MSP(*(__IO uint32_t *)app_address);

    app_reset_handler();
}
