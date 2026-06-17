# OCTPhantomVirtualScanning.py (ФИНАЛЬНАЯ БЕЗОПАСНАЯ ВЕРСИЯ)

import configparser
import time
import numpy as np
import scipy.stats
from scipy.io import savemat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from multiprocessing import Pool, cpu_count
import os
from tqdm import tqdm
import argparse
from numba import jit
import sys
import io
import psutil

# --- FIX FOR WINDOWS ---
# Force UTF-8 encoding for standard output to avoid
# issues with cp1251 on Windows.
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
# --------------------------------

IM1 = 1j

def auto_scale_processes():
    """Автоматическое масштабирование количества процессов на основе системных ресурсов"""
    try:
        # Получаем текущую нагрузку системы
        cpu_percent = psutil.cpu_percent(interval=0.5)  # Быстрее измерение
        memory_percent = psutil.virtual_memory().percent
        available_cores = cpu_count()
        
        print(f"[Auto-Scale] CPU: {cpu_percent:.1f}%, Memory: {memory_percent:.1f}%, Cores: {available_cores}")
        
        # Проверяем переменную окружения для принудительного режима
        force_performance = os.getenv('FORCE_PERFORMANCE_MODE', 'false').lower() == 'true'
        
        if force_performance:
            # Принудительный режим производительности - используем больше процессов
            optimal_processes = min(16, available_cores * 2)
            print(f"[Auto-Scale] ПРИНУДИТЕЛЬНЫЙ РЕЖИМ ПРОИЗВОДИТЕЛЬНОСТИ: {optimal_processes} процессов")
        elif cpu_percent < 30 and memory_percent < 60:
            # Система свободна - агрессивный режим
            optimal_processes = min(16, available_cores * 2)
            print(f"[Auto-Scale] Низкая нагрузка - агрессивный режим: {optimal_processes} процессов")
        elif cpu_percent < 60 and memory_percent < 80:
            # Умеренная нагрузка - можно использовать больше процессов
            optimal_processes = min(12, available_cores)
            print(f"[Auto-Scale] Умеренная нагрузка - используем {optimal_processes} процессов")
        elif cpu_percent < 80 and memory_percent < 90:
            # Высокая нагрузка - уменьшаем количество процессов
            optimal_processes = max(4, available_cores // 2)
            print(f"[Auto-Scale] Высокая нагрузка - используем {optimal_processes} процессов")
        else:
            # Критическая нагрузка - минимальное количество
            optimal_processes = max(2, available_cores // 4)
            print(f"[Auto-Scale] Критическая нагрузка - используем {optimal_processes} процессов")
        
        return optimal_processes
        
    except Exception as e:
        print(f"[Auto-Scale] Ошибка мониторинга: {e}, используем стандартное значение")
        return min(8, cpu_count())

# Все функции (worker_function, setup_worker_globals, fun_sa23c_optimized_v2, _calculate_fftS_numba)
# остаются в глобальной области видимости, чтобы их можно было импортировать.

g_xs = g_ys = g_zs0 = g_Ka_wavenumbers = g_Asc_amplitudes = None
g_W_window = g_N_pixels = g_ScatTransp_coeffs = g_Zs0idx_sorted_indices = g_num_scatterers = None

def setup_worker_globals(xs, ys, zs0, Ka_wavenumbers, Asc_amplitudes, W_window, N_pixels, ScatTransp_coeffs, Zs0idx_sorted_indices, num_scatterers):
    global g_xs, g_ys, g_zs0, g_Ka_wavenumbers, g_Asc_amplitudes, g_W_window, g_N_pixels, g_ScatTransp_coeffs, g_Zs0idx_sorted_indices, g_num_scatterers
    g_xs, g_ys, g_zs0 = xs, ys, zs0
    g_Ka_wavenumbers, g_Asc_amplitudes = Ka_wavenumbers, Asc_amplitudes
    g_W_window, g_N_pixels = W_window, N_pixels
    g_ScatTransp_coeffs, g_Zs0idx_sorted_indices, g_num_scatterers = ScatTransp_coeffs, Zs0idx_sorted_indices, num_scatterers

def worker_function(task_args):
    w0_beam_radius, current_xA, current_yA = task_args
    return fun_sa23c_optimized_v2(w0_beam_radius, current_xA, g_xs, current_yA, g_ys, g_zs0, g_Ka_wavenumbers, g_Asc_amplitudes, g_W_window, g_N_pixels, g_ScatTransp_coeffs, g_Zs0idx_sorted_indices, g_num_scatterers)

@jit(nopython=True, fastmath=True, cache=True)
def _calculate_fftS_numba(w0_beam_radius, current_xA, xs_scatterers, current_yA, ys_scatterers, zs_scatterers,
                          Ka_wavenumbers, Asc_amplitudes, N_pixels,
                          ScatTransp_coeffs, Zs0idx_sorted_indices, num_scatterers):
    IM1_local = 1j
    fftS = np.zeros(N_pixels, dtype=np.complex128)
    EProd = np.ones(num_scatterers, dtype=np.float64)
    Bs = np.exp(-(((current_xA - xs_scatterers)**2 + (current_yA - ys_scatterers)**2) / w0_beam_radius**2))
    if num_scatterers > 1:
        for i in range(1, num_scatterers):
            idx_curr_original = Zs0idx_sorted_indices[i]
            idx_prev_original = Zs0idx_sorted_indices[i - 1]
            EProd[idx_curr_original] = EProd[idx_prev_original] * (1 - (Bs[idx_prev_original] * ScatTransp_coeffs[idx_prev_original])**2)
    for kla_idx in range(N_pixels):
        Us_col = np.exp(-IM1_local * (Ka_wavenumbers[kla_idx] * zs_scatterers))
        for ppq_loop_idx in range(num_scatterers):
            original_idx = Zs0idx_sorted_indices[ppq_loop_idx]
            if ((current_xA - xs_scatterers[original_idx])**2 + (current_yA - ys_scatterers[original_idx])**2) < 3 * w0_beam_radius**2:
                sqrt_EProd_val = np.sqrt(EProd[original_idx])
                AscScatt = sqrt_EProd_val * ScatTransp_coeffs[original_idx] * Bs[original_idx]
                AscDetect = AscScatt * sqrt_EProd_val * Us_col[original_idx]
                fftS[kla_idx] += AscDetect * np.exp(-IM1_local * Ka_wavenumbers[kla_idx] * zs_scatterers[original_idx])
    return fftS

def fun_sa23c_optimized_v2(w0_beam_radius, current_xA, xs_scatterers, current_yA, ys_scatterers, zs_scatterers,
                           Ka_wavenumbers, Asc_amplitudes, W_window, N_pixels,
                           ScatTransp_coeffs, Zs0idx_sorted_indices, num_scatterers):
    fftS = _calculate_fftS_numba(w0_beam_radius, current_xA, xs_scatterers, current_yA, ys_scatterers, zs_scatterers,
                                 Ka_wavenumbers, Asc_amplitudes, N_pixels,
                                 ScatTransp_coeffs, Zs0idx_sorted_indices, num_scatterers)
    ifftS_row = np.fft.ifft(fftS * W_window)
    Zap_out = np.zeros(2 * N_pixels, dtype=np.float64)
    Zap_out[0::2] = np.real(ifftS_row)
    Zap_out[1::2] = np.imag(ifftS_row)
    return Zap_out

def run_oct_simulation(config_file_path='Configuration.ini'):
    overall_start_time = time.time()
    print(f"Start program using config: {config_file_path}")
    config = configparser.ConfigParser()
    config.optionxform = str
    if not os.path.exists(config_file_path):
        print(f"ERROR: Config file not found: {config_file_path}"); return
    config.read(config_file_path)
    params = config['Parameters']
    FRes1 = params.get('Scan Filename', 'OutputFile1.dat')
    scatterers_filename = params.get('Scatterers coordinates File', 'patient01_slice0_var0_scatterers.dat')
    config_dir = os.path.dirname(config_file_path) if os.path.dirname(config_file_path) else '.'
    FScat = os.path.join(config_dir, scatterers_filename)
    N_pixels = params.getint('A-scan pixel numbers', 512)
    Hpx_mcm = params.getfloat('Vertical pixel size mcm', 5)
    la0_mcm = params.getfloat('Central wavelength mcm', 1.3)
    Ascans = params.getint('Number of A-scans in B-scan', 512)
    Xmax_mcm = params.getfloat('Xmax mcm', 1500)
    Bscans = params.getint('Number of B-scans', 1)
    w0_beam_radius_mcm = params.getfloat('Beam Radius mcm', 10)
    num_scatterers_config = params.getint('Number of scatterers in B-scan', 114914)
    output_dir_for_scan = os.path.dirname(config_file_path) if os.path.dirname(config_file_path) else '.'
    FRes1_path = os.path.join(output_dir_for_scan, FRes1)
    base_output_name = os.path.splitext(FRes1)[0]
    mat_output_path = os.path.join(output_dir_for_scan, f"{base_output_name}_ScanData.mat")
    png_output_path_template = os.path.join(output_dir_for_scan, f"{base_output_name}_Image")
    try:
        output_file_scan = open(FRes1_path, 'wb')
    except IOError:
        print(f"Error: Cannot open file {FRes1_path} for writing."); return
    H_depth_mcm = Hpx_mcm * (N_pixels - 1)
    np.random.seed(0)
    if not os.path.exists(FScat):
        print(f'Scatterers file "{FScat}" not found. Skipping simulation.'); output_file_scan.close(); return
    try:
        XYZA = np.loadtxt(FScat)
        LoadedScat = XYZA.shape[0]
        Scat_actual = num_scatterers_config if 0 < num_scatterers_config <= LoadedScat else LoadedScat
        xs, ys, zs0, Asc_amplitudes = XYZA[:Scat_actual, 0], XYZA[:Scat_actual, 1], XYZA[:Scat_actual, 2], XYZA[:Scat_actual, 3]
        print(f'Loaded {Scat_actual} scatterers from {FScat}.')
    except Exception as e:
        print(f"Error loading scatterers file {FScat}: {e}"); output_file_scan.close(); return
    num_scatterers = Scat_actual
    dk_wavenum_step = np.pi / H_depth_mcm * N_pixels / (N_pixels + 1)
    k0_central_wavenum = 2 * np.pi / la0_mcm
    W_window = np.fft.ifftshift(np.hanning(N_pixels))
    la_wavelengths = 2 * np.pi / (np.arange(0, N_pixels) * dk_wavenum_step + k0_central_wavenum - (N_pixels // 2) * dk_wavenum_step)
    Ka_wavenumbers = 2 * np.pi / la_wavelengths
    xA_coords = np.linspace(-Xmax_mcm, Xmax_mcm, Ascans)
    Zs0idx_sorted_indices = np.argsort(zs0)
    ThansparencyCoeff = 0.1
    ScatTransp_coeffs = ThansparencyCoeff * Asc_amplitudes

    tasks = [(w0_beam_radius_mcm, xA, 0.0) for xA in xA_coords]
    initializer_args = (xs, ys, zs0, Ka_wavenumbers, Asc_amplitudes, W_window, N_pixels, ScatTransp_coeffs, Zs0idx_sorted_indices, num_scatterers)

    # Автоматическое масштабирование ресурсов
    num_processes = auto_scale_processes()
    print(f"Starting A-scan generation using {num_processes} processes...")
    
    # Инициализируем глобальные переменные для разминки Numba
    setup_worker_globals(*initializer_args)
    print("  - Numba JIT compiler is warming up...")
    if tasks: worker_function(tasks[0])
    print("  - Numba is ready.")
    scan_gen_start_time = time.time()
    
    # --- ИЗМЕНЕНИЕ: Весь блок Pool теперь внутри main_process ---
    # Это гарантирует, что он не будет вызван при импорте
    # Эта функция будет вызвана только при прямом запуске скрипта
    def main_process():
        with Pool(processes=num_processes, initializer=setup_worker_globals, initargs=initializer_args) as pool:
            # Оптимизируем chunksize для максимальной производительности
            optimal_chunksize = max(1, Ascans // (num_processes * 2))
            results_iterator = pool.imap(worker_function, tasks, chunksize=optimal_chunksize)
            return list(tqdm(results_iterator, total=Ascans, desc="Generating A-scans", mininterval=1.0, file=sys.stdout))

    # Вызываем функцию, которая запускает Pool
    Zap_results_list = main_process()
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---
        
    scan_gen_duration = time.time() - scan_gen_start_time
    print(f"A-scan generation finished in {scan_gen_duration:.2f} seconds.")

    Zap_all_ascans = np.array(Zap_results_list)
    output_file_scan.write(Zap_all_ascans.astype(np.float32).tobytes())
    output_file_scan.close()
    print(f'{FRes1_path} saved.')
    real_parts, imag_parts = Zap_all_ascans[:, 0::2], Zap_all_ascans[:, 1::2]
    Scan_X_Y = real_parts + IM1 * imag_parts
    savemat(mat_output_path, {'Scan_X_Y': Scan_X_Y}, do_compression=True)
    print(f'{mat_output_path} saved')
    SigToImg_dB = (20 * np.log10(np.abs(Scan_X_Y) + np.finfo(float).eps)).T
    Max1_dB = np.max(SigToImg_dB)
    Aim_image_data = SigToImg_dB - Max1_dB + 40
    display_min = np.max([np.min(Aim_image_data), 0])
    display_max = np.max(Aim_image_data)
    if display_max <= display_min: display_max = display_min + 1
    plt.imsave(f'{png_output_path_template}_gray.png', Aim_image_data, cmap='gray', vmin=display_min, vmax=display_max)
    print(f'{png_output_path_template}_gray.png saved')
    print(f'Total execution time: {time.time() - overall_start_time:.2f} seconds')

# --- ИЗМЕНЕНИЕ: Весь исполняемый код теперь внутри этой защитной конструкции ---
if __name__ == '__main__':
    # Эта защита критически важна для multiprocessing на Windows и в сложных средах
    cli_parser = argparse.ArgumentParser(description="Запускает симуляцию ОКТ сканирования.")
    cli_parser.add_argument('--config', type=str, default='Configuration.ini', help='Путь к файлу конфигурации .ini')
    args = cli_parser.parse_args()
    run_oct_simulation(config_file_path=args.config)