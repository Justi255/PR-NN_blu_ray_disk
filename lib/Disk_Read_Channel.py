import sys
import os
import numpy as np
sys.path.append(
    os.path.dirname(
        os.path.abspath(__file__)))
from Const import RLL_state_machine
from Channel_Modulator import RLL_Modulator
from Channel_Converter import NRZI_Converter
from Disk_Response import BD_symbol_response
from Utils import plot_separated
sys.path.pop()
import pdb

info_len = 80
tap_bd_num = 6
snr_start =20
snr_stop =60
snr_step =10
    
class Disk_Read_Channel(object):
    
    def __init__(self):
        _, bd_di_coef = BD_symbol_response(bit_periods = 10)
        mid_idx = len(bd_di_coef)//2
        self.bd_di_coef = bd_di_coef[mid_idx : mid_idx + tap_bd_num].reshape(1,-1)
        self.len_dummy = self.bd_di_coef.shape[1]
        
        print('The dipulse bd coefficient is\n')
        print(bd_di_coef)
        print('Tap bd coefficient is\n')
        print(self.bd_di_coef)
        print('Len Dummy is\n')
        print(self.len_dummy)
    
    def RF_signal(self, codeword):
        length = codeword.shape[1] - self.len_dummy
        codeword = np.pad(codeword[:,:length], ((0, 0), (0, self.len_dummy)), mode='constant')
        rf_signal = (np.convolve(self.bd_di_coef[0, :], codeword[0, :])
               [:-(tap_bd_num - 1)].reshape(codeword.shape))
        
        return rf_signal
    
    def awgn(self, x, snr):
        E_b = 1
        sigma = np.sqrt(0.5 * E_b * 10 ** (- snr * 1.0 / 10))
        return x + sigma * np.random.normal(0, 1, x.shape)
    
if __name__ == '__main__':
    
    # constant and input paras
    encoder_dict, encoder_definite = RLL_state_machine()
    RLL_modulator = RLL_Modulator(encoder_dict, encoder_definite)
    NRZI_converter = NRZI_Converter()
    disk_read_channel = Disk_Read_Channel()
    
    num_ber = int((snr_stop-snr_start)/snr_step+1)
    
    code_rate = 2/3
    Normalized_t = np.linspace(1, int(info_len/code_rate), int(info_len/code_rate))
    
    for idx in np.arange(0, num_ber):
        snr = snr_start+idx*snr_step
        
        info = np.random.randint(2, size = (1, info_len))
        codeword = NRZI_converter.forward_coding(RLL_modulator.forward_coding(info))
        rf_signal = disk_read_channel.RF_signal(codeword)
        equalizer_input = disk_read_channel.awgn(rf_signal, snr)
        
        Xs = [
            Normalized_t,
            Normalized_t,
            Normalized_t
        ]
        Ys = [
           {'data': codeword.reshape(-1), 'label': 'binary Sequence'}, 
           {'data': rf_signal.reshape(-1), 'label': 'rf_signal', 'color': 'red'},
           {'data': equalizer_input.reshape(-1), 'label': f'equalizer_input_snr{snr}', 'color': 'red'}
        ]
        titles = [
            'Binary Sequence',
            'rf_signal',
            f'equalizer_input_snr{snr}'
        ]
        xlabels = ["Time (t/T)"]
        ylabels = [
            "Binary",
            "Amplitude",
            "Amplitude"
        ]
        plot_separated(
            Xs=Xs, 
            Ys=Ys, 
            titles=titles,     
            xlabels=xlabels, 
            ylabels=ylabels
        )