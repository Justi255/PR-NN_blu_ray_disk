import argparse
import numpy as np
import sys
np.set_printoptions(threshold=sys.maxsize)

from lib.Const import RLL_state_machine, Target_channel_state_machine
from lib.Channel_Modulator import RLL_Modulator
from lib.Channel_Converter import NRZI_Converter
from lib.Disk_Read_Channel import Disk_Read_Channel
from lib.Target_PR_Channel import Target_PR_Channel
from lib.Adaptive_Equalizer import Adaptive_Equalizer
from lib.Utils import plot_separated, find_index

import pdb

np.random.seed(12345)

parser = argparse.ArgumentParser()

parser.add_argument('-info_len', type=int, default=1000000)
parser.add_argument('-equalizer_train_len', type=int, default=1000)
parser.add_argument('-truncation_len', type=int, default=30)
parser.add_argument('-overlap_len', type=int, default=30)

parser.add_argument('-snr_start', type=float, default=8.5)
parser.add_argument('-snr_stop', type=float, default=12.5)
parser.add_argument('-snr_step', type=float, default=0.5)

global args
args = parser.parse_args()

def realistic_sys():
    
    # constant and input paras
    encoder_dict, encoder_definite = RLL_state_machine()
    channel_dict, dummy_dict, ini_metric = Target_channel_state_machine()
    
    # rate for constrained code
    num_sym_in_constrain = encoder_dict[1]['input'].shape[1]
    num_sym_out_constrain = encoder_dict[1]['output'].shape[1]
    rate_constrain = num_sym_in_constrain / num_sym_out_constrain
    dummy_len = int(args.overlap_len * num_sym_in_constrain 
                 / num_sym_out_constrain)
    codeword_len = int(args.info_len/rate_constrain)
    
    # class
    RLL_modulator = RLL_Modulator(encoder_dict, encoder_definite)
    NRZI_converter = NRZI_Converter()
    disk_read_channel = Disk_Read_Channel()
    target_pr_channel = Target_PR_Channel(channel_dict, dummy_dict, channel_dict['ini_state'])
    viterbi_decoder = Viterbi(channel_dict, ini_metric)
    
    # train mode 
    # Initial Convergence of Tap Coefficients for Adaptive Equalizers
    snr = args.snr_start
    train_bits = np.random.randint(2, size = (1, args.equalizer_train_len+dummy_len))
    codeword = NRZI_converter.forward_coding(RLL_modulator.forward_coding(train_bits))
    rf_signal = disk_read_channel.RF_signal(codeword)
    equalizer_input = disk_read_channel.awgn(rf_signal, snr)
    pr_signal = target_pr_channel.target_channel(codeword)
    pr_adaptive_equalizer = Adaptive_Equalizer(        
        equalizer_input  = equalizer_input.reshape(-1),
        reference_signal = pr_signal.reshape(-1),
        taps_num = 9,
        mu = 0.01
    )
    _, _, _, _ = pr_adaptive_equalizer.lms()
    
    # define ber
    num_ber = int((args.snr_stop-args.snr_start)/args.snr_step+1)
    ber_channel = np.zeros((1, num_ber))
    ber_info = np.zeros((1, num_ber))
    
    # eval mode
    for idx in np.arange(0, num_ber):
        snr = args.snr_start+idx*args.snr_step
        
        info = np.random.randint(2, size = (1, args.info_len+dummy_len))
        codeword = NRZI_converter.forward_coding(RLL_modulator.forward_coding(info))
        
        rf_signal = disk_read_channel.RF_signal(codeword)
        equalizer_input_real = disk_read_channel.awgn(rf_signal, snr)
        
        length = equalizer_input_real.shape[1]
        decodeword = np.empty((1, 0))
        for pos in range(0, length - args.overlap_len, args.truncation_len):
            
            equalizer_input_truncation = equalizer_input_real[:, pos:pos+args.truncation_len+args.overlap_len]
            
            pr_adaptive_equalizer.equalizer_input = equalizer_input_truncation.reshape(-1)
            detector_input = pr_adaptive_equalizer.equalized_signal()
            detector_input = detector_input.reshape(1,-1)
            
            dec_tmp, metric_next = viterbi_decoder.vit_dec(detector_input, ini_metric)
            ini_metric = metric_next
            decodeword = np.append(decodeword, dec_tmp, axis=1)
            
            # # eval mode 
            # # Guarantees that the equalizer can track changes in channel characteristics
            # # dec_tmp may not satisfy RLL(1,7) and NRZI constrained code
            # rf_signal = disk_read_channel.RF_signal(dec_tmp)
            # equalizer_input = disk_read_channel.awgn(rf_signal, snr)
            # pr_signal = target_pr_channel.target_channel(dec_tmp)
            # pr_adaptive_equalizer.equalizer_input  = equalizer_input
            # pr_adaptive_equalizer.reference_signal = pr_signal
            # _, _, _, _ = pr_adaptive_equalizer.lms()
        
        print("The SNR is:")
        print(snr)
        ber = (np.count_nonzero(np.abs(codeword[:, 0:codeword_len] - decodeword[:, 0:codeword_len])) 
               / codeword_len)
        print("The bit error rate (BER) is:")
        print(ber)

def test_sys():
    
    # constant and input paras
    encoder_dict, encoder_definite = RLL_state_machine()
    channel_dict, dummy_dict, ini_metric = Target_channel_state_machine()
    
    # rate for constrained code
    num_sym_in_constrain = encoder_dict[1]['input'].shape[1]
    num_sym_out_constrain = encoder_dict[1]['output'].shape[1]
    rate_constrain = num_sym_in_constrain / num_sym_out_constrain
    dummy_len = int(args.overlap_len * num_sym_in_constrain 
                 / num_sym_out_constrain)
    codeword_len = int(args.info_len/rate_constrain)
    
    # class
    RLL_modulator = RLL_Modulator(encoder_dict, encoder_definite)
    NRZI_converter = NRZI_Converter()
    target_pr_channel = Target_PR_Channel(channel_dict, dummy_dict, channel_dict['ini_state'])
    viterbi_decoder = Viterbi(channel_dict, ini_metric)
    
    # define ber
    num_ber = int((args.snr_stop-args.snr_start)/args.snr_step+1)
    ber_channel = np.zeros((1, num_ber))
    ber_info = np.zeros((1, num_ber))
    
    for idx in np.arange(0, num_ber):
        snr = args.snr_start+idx*args.snr_step
        
        info = np.random.randint(2, size = (1, args.info_len+dummy_len))
        codeword = NRZI_converter.forward_coding(RLL_modulator.forward_coding(info))
        
        pr_signal = target_pr_channel.target_channel(codeword)
        detector_input_target_pr = target_pr_channel.awgn(pr_signal, snr)
        
        length = detector_input_target_pr.shape[1]
        decodeword = np.empty((1, 0))
        for pos in range(0, length - args.overlap_len, args.truncation_len):
            detector_input_target_pr_truncation = detector_input_target_pr[:, pos:pos+args.truncation_len+args.overlap_len]
            dec_tmp, metric_next = viterbi_decoder.vit_dec(detector_input_target_pr_truncation, ini_metric)
            ini_metric = metric_next
            decodeword = np.append(decodeword, dec_tmp, axis=1)
        
        print("The SNR is:")
        print(snr)
        ber = (np.count_nonzero(np.abs(codeword[:, 0:codeword_len] - decodeword[:, 0:codeword_len])) 
               / codeword_len)
        print("The bit error rate (BER) is:")
        print(ber)

## Decoder: Viterbi decoder
class Viterbi(object):
    def __init__(self, channel_machine, ini_metric):
        self.channel_machine = channel_machine
        self.ini_metric = ini_metric
        self.num_state = self.channel_machine['num_state']
    
    def vit_dec(self, r_truncation, ini_metric):
        
        r_len = r_truncation.shape[1]
        ini_metric_trun = ini_metric
        path_survivor = np.zeros((self.num_state, r_len))
        state_metric_trun = np.zeros((self.num_state, args.truncation_len))
        
        for idx in range(r_len):
            state_path, state_metric = self.metric(r_truncation[:, idx], 
                                                   ini_metric_trun)
            
            ini_metric_trun = state_metric
            path_survivor[:, idx:idx+1] = state_path
            if idx == args.truncation_len-1:
                state_metric_next = state_metric
        
        state_min = np.argmin(state_metric, axis=0)[0]
        path = self.path_convert(path_survivor)
        dec_word = self.path_to_word(path, state_min)
        
        return dec_word[:, :args.truncation_len], state_metric_next
        
    def metric(self, r, metric_last):
        '''
        Input: branch metrics at one time step
        Output: branch metric and survivor metric for the next step 
        Mapping: choose the shorest path between adjacent states
        '''
        
        path_survivor, metric_survivor = (np.zeros((self.num_state, 1)), 
                                          np.zeros((self.num_state, 1)))
        
        for state in range(self.num_state):
            set_in = np.where(self.channel_machine['state_machine'][:, 1]==state)[0]
            metric_tmp = np.zeros((set_in.shape[0], 1))
            for i in range(set_in.shape[0]):
                metric_tmp[i, :] = (metric_last[self.channel_machine['state_machine'][set_in[i], 0], :][0] + 
                                    self.euclidean_distance(r, self.channel_machine['in_out'][set_in[i], 1]))
            metric_survivor[state, :] = metric_tmp.min()
            # if we find equal minimum branch metric, we choose the upper path
            path_survivor[state, :] = (
                self.channel_machine['state_machine'][set_in[np.where(metric_tmp==metric_tmp.min())[0][0]], 0])
        return path_survivor, metric_survivor
                
    
    def path_convert(self, path_survivor):
        '''
        Input: (num_state, length) array
        Output: (num_state, length) array
        Mapping: Viterbi decoder for a truncation part
        '''
        
        path_truncation = np.zeros(path_survivor.shape)
        path_truncation[:, -1:] = path_survivor[:, -1:]
        for state in range(self.num_state):
            for i in range(path_survivor.shape[1]-2, -1, -1):
                path_truncation[state, i] = int(path_survivor[
                    int(path_truncation[state, i+1]), i])
        
        return path_truncation

    def path_to_word(self, path, state):
        '''
        Input: (1, length) array
        Output: (1, length-1) array
        Mapping: connection between two states determines one word
        '''
        
        length = path.shape[1]
        word = np.zeros((1, length-1))
        for i in range(length-1):
            idx = find_index(self.channel_machine['state_machine'], path[state, i : i+2])
            word[:, i] = self.channel_machine['in_out'][idx, 0]
        
        return word
    
    def path_to_word_test(self, path, state):
        '''
        Input: (1, length) array
        Output: (1, length) array
        Mapping: connection between two states determines one word
        '''
        
        length = path.shape[1]
        word = np.zeros((1, length))
        for i in range(length-1):
            idx = find_index(self.channel_machine['state_machine'], path[state, i : i+2])
            word[:, i] = self.channel_machine['in_out'][idx, 0]
        
        idx = find_index(self.channel_machine['state_machine'], np.array([path[state, -1], state]))
        word[:, -1] = self.channel_machine['in_out'][idx, 0]
        return word
    
    def euclidean_distance(self, x, y):
        return np.sum((x - y) ** 2)

if __name__ == '__main__':
    realistic_sys()
    # test_sys()