# converter.py
import os
import numpy as np
import cv2
import scipy.io
from tqdm import tqdm
import warnings

# --- НАСТРОЙКИ ---
MAT_FILE_PATH = 'skin_db.mat'
OUTPUT_PNG_DIR = 'real_scans_png'
# --------------------


def load_skin_db_from_mat(mat_file_path):
    """
    Вспомогательная функция для загрузки данных из skin_db.mat.
    """
    try:
        if not os.path.exists(mat_file_path):
            raise FileNotFoundError(f"Файл '{mat_file_path}' не найден.")

        print(f"Загрузка данных из '{mat_file_path}'...")
        data = scipy.io.loadmat(mat_file_path, squeeze_me=True, struct_as_record=False)
        skindb = data.get('skin_db')

        if skindb is None:
            print(f"Ошибка: Структура 'skin_db' не найдена в файле {mat_file_path}.")
            return None

        patients = {}
        patient_keys_found = False
        for attr in dir(skindb):
            if attr.startswith('patient'):
                patients[attr] = getattr(skindb, attr)
                patient_keys_found = True

        if not patient_keys_found:
            print(f"Ошибка: Данные пациентов ('patient*') не найдены в файле {mat_file_path}.")
            return None

        print("Данные успешно загружены.")
        return patients

    except Exception as e:
        print(f"Критическая ошибка при загрузке MAT-файла '{mat_file_path}': {e}")
        return None


def convert_real_data_to_png(input_mat_path, output_dir):
    """
    Основная функция, которая читает .mat файл, извлекает все ОКТ-сканы
    и сохраняет их как PNG изображения.
    """
    print(f"\n--- Начало конвертации ---")

    os.makedirs(output_dir, exist_ok=True)
    print(f"Изображения будут сохранены в папку: '{os.path.abspath(output_dir)}'")

    patients_data = load_skin_db_from_mat(input_mat_path)
    if not patients_data:
        print("Конвертация прервана из-за ошибки загрузки данных.")
        return

    total_scans_processed = 0

    for patient_key, patient_obj in tqdm(patients_data.items(), desc="Обработка пациентов"):
        try:
            if not hasattr(patient_obj, 'oct') or patient_obj.oct is None or patient_obj.oct.ndim != 3:
                warnings.warn(f"\nПредупреждение: У пациента '{patient_key}' отсутствуют или некорректны данные ОКТ. Пропускаем.")
                continue

            num_scans = patient_obj.oct.shape[2]

            for scan_idx in range(num_scans):
                raw_image = patient_obj.oct[:, :, scan_idx]
                if raw_image is None:
                    continue

                min_val, max_val = np.min(raw_image), np.max(raw_image)
                if max_val > min_val:
                    image_normalized = ((raw_image.astype(np.float32) - min_val) / (max_val - min_val) * 255.0).astype(np.uint8)
                else:
                    image_normalized = raw_image.astype(np.uint8)

                base_filename = f"{patient_key}_scan_{scan_idx+1:03d}.png"
                img_save_path = os.path.join(output_dir, base_filename)

                cv2.imwrite(img_save_path, image_normalized)
                total_scans_processed += 1

        except Exception as e:
            warnings.warn(f"\nНепредвиденная ошибка при обработке пациента '{patient_key}': {e}")

    print(f"\n--- Конвертация завершена ---")
    # --- ИЗМЕНЕНО: Убран эмодзи, вызывающий ошибку в Windows ---
    print(f"Всего обработано и сохранено: {total_scans_processed} изображений.")


if __name__ == '__main__':
    convert_real_data_to_png(MAT_FILE_PATH, OUTPUT_PNG_DIR)