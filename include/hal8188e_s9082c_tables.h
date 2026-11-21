#ifndef __HAL8188E_S9082C_TABLES_H__
#define __HAL8188E_S9082C_TABLES_H__

#include <drv_types.h>

static inline u32 s9082_bit_reverse32(u32 val)
{
	u32 w0 = val;
	u32 w1 = ((w0 & 0xaaaaaaaa) >> 1) | ((w0 & 0x55555555) << 1);
	w0 = ((w1 & 0xcccccccc) >> 2) | ((w1 & 0x33333333) << 2);
	return ((w0 & 0xf0f0f0f0) >> 4) | ((w0 & 0x0f0f0f0f) << 4);
}

static inline u8 s9082_bit_reverse8(u8 val)
{
	u8 w0 = val;
	u8 w1 = ((w0 & 0xaa) >> 1) | ((w0 & 0x55) << 1);
	w0 = ((w1 & 0xcc) >> 2) | ((w1 & 0x33) << 2);
	return ((w0 & 0xf0) >> 4) | ((w0 & 0x0f) << 4);
}

static inline u16 s9082_bit_reverse16(u16 val)
{
	u16 w0 = val;
	u16 w1 = ((w0 & 0xaaaa) >> 1) | ((w0 & 0x5555) << 1);
	w0 = ((w1 & 0xcccc) >> 2) | ((w1 & 0x3333) << 2);
	return ((w0 & 0xf0f0) >> 4) | ((w0 & 0x0f0f) << 4);
}

extern const u32 array_mp_s9082c_radioa[];
extern const u32 array_mp_s9082c_radioa_size;

extern const u32 array_mp_s9082c_phy_reg[];
extern const u32 array_mp_s9082c_phy_reg_size;

extern const u32 array_mp_s9082c_agc_tab[];
extern const u32 array_mp_s9082c_agc_tab_size;

extern const u32 array_mp_s9082c_mac_reg[];
extern const u32 array_mp_s9082c_mac_reg_size;

int s9082c_mac_config(PADAPTER Adapter);
int s9082c_bb_config(PADAPTER Adapter);
int s9082c_rf8353_config(PADAPTER Adapter);

u32 s9082c_read_bbreg(PADAPTER Adapter, u32 RegAddr, u32 BitMask);
void s9082c_write_bbreg(PADAPTER Adapter, u32 RegAddr, u32 BitMask, u32 Data);
u32 s9082c_read_rfreg(PADAPTER Adapter, enum rf_path eRFPath, u32 RegAddr, u32 BitMask);
void s9082c_write_rfreg(PADAPTER Adapter, enum rf_path eRFPath, u32 RegAddr, u32 BitMask, u32 Data);
void s9082c_set_chnl_bw(PADAPTER Adapter, u8 channel, enum channel_width Bandwidth, u8 Offset40, u8 Offset80);
void s9082c_set_bcn_related_regs(PADAPTER padapter);
void s9082c_lc_calibrate(PADAPTER Adapter);
void s9082c_iq_calibrate(PADAPTER Adapter);
void s9082c_set_rf_path_switch(PADAPTER Adapter, bool is_main);

#endif /* __HAL8188E_S9082C_TABLES_H__ */
