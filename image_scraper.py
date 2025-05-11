import os
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from urllib.parse import urljoin

# --- Настройка Selenium --- 
# Убедитесь, что у вас установлен WebDriver (например, chromedriver)
# и он доступен в PATH, или укажите путь к нему:
# options = webdriver.ChromeOptions()
# options.add_argument('--headless') # Запуск в фоновом режиме (без GUI)
# driver = webdriver.Chrome(options=options) 
# Или:
# driver = webdriver.Firefox() 
# ---

def download_images(url, save_dir):
    """Загружает изображения со слайдера на странице и сохраняет их."""
    print(f"Обработка URL: {url}")
    driver = None # Инициализируем driver
    try:
        # Используем Selenium для загрузки страницы
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless') # Раскомментируйте для фонового режима
        # Укажите путь к chromedriver, если он не в PATH
        # driver = webdriver.Chrome(executable_path='/path/to/chromedriver', options=options)
        driver = webdriver.Chrome(options=options)
        driver.get(url)

        # Ждем, пока изображения в слайдере загрузятся (настраиваемое время и селектор)
        wait_time = 10 # Секунд ожидания
        # Используем селектор, подтвержденный через Puppeteer
        slider_selector = 'div#masterslider_div img' # Более точный селектор для слайдера 
        try:
            WebDriverWait(driver, wait_time).until(
                # Ждем присутствия хотя бы одного элемента, соответствующего селектору
                EC.presence_of_element_located((By.CSS_SELECTOR, slider_selector))
            )
            print("Элементы слайдера найдены.")
            # Дополнительная пауза, если контент подгружается динамически после появления первого элемента
            time.sleep(3) 
        except TimeoutException:
            print(f"Основные изображения ('{slider_selector}') не найдены или не загрузились за {wait_time} секунд на {url}")
            # Попробуем найти любые изображения как запасной вариант
            fallback_selector = 'img' 
            try:
                 WebDriverWait(driver, 5).until(
                    # Используем fallback_selector для ожидания любых изображений
                    EC.presence_of_element_located((By.CSS_SELECTOR, fallback_selector))
                 )
                 print("Найдены другие изображения (используется fallback_selector).")
                 time.sleep(2)
                 # Получаем HTML и парсим с fallback_selector
                 page_source = driver.page_source
                 soup = BeautifulSoup(page_source, 'html.parser')
                 image_tags = soup.select(fallback_selector) # Используем fallback_selector
            except TimeoutException:
                 print(f"Вообще не найдено изображений (даже с fallback_selector='{fallback_selector}') на {url}")
                 driver.quit()
                 return
        else:
            # Этот блок выполняется, если основной WebDriverWait НЕ вызвал TimeoutException
            # Получаем HTML и парсим с основным slider_selector
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            image_tags = soup.select(slider_selector) # Используем основной slider_selector

        if not image_tags:
            print(f"Изображения не найдены на {url}")
            return

        # Создаем подпапку для URL (используем часть URL или заголовок страницы)
        # Простой вариант: использовать последние части URL
        folder_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', url.split('/')[-2] or url.split('/')[-1] or 'page')
        page_save_dir = os.path.join(save_dir, folder_name)
        os.makedirs(page_save_dir, exist_ok=True)
        print(f"Сохранение в папку: {page_save_dir}")

        for i, img_tag in enumerate(image_tags):
            img_url = img_tag.get('src') # Или 'data-src', или другой атрибут
            if not img_url:
                continue

            # Обработка относительных URL
            if not img_url.startswith(('http://', 'https://')):
                img_url = urljoin(url, img_url)

            try:
                img_response = requests.get(img_url)
                img_response.raise_for_status()
                img_data = BytesIO(img_response.content)
                img = Image.open(img_data)

                # Сохраняем изображение
                img_filename = f"image_{i+1}.{img.format.lower() or 'jpg'}"
                img_save_path = os.path.join(page_save_dir, img_filename)
                with open(img_save_path, 'wb') as f:
                    f.write(img_response.content)
                print(f"Сохранено: {img_filename}")

            except requests.exceptions.RequestException as e:
                print(f"Ошибка загрузки изображения {img_url}: {e}")
            except Exception as e:
                 print(f"Ошибка обработки изображения {img_url}: {e}")

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при запросе страницы или изображения {url}: {e}")
    except Exception as e:
        print(f"Непредвиденная ошибка при обработке {url}: {e}")
    finally:
        if driver:
            driver.quit() # Обязательно закрываем браузер

def stitch_images(folder_path):
    """Склеивает все изображения в папке вертикально, масштабируя по ширине."""
    print(f"Склеивание изображений в папке: {folder_path}")
    image_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith(('png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'))])

    if not image_files:
        print("Нет изображений для склеивания.")
        return

    max_width = 0
    images_data = [] # Список для хранения данных изображений: (путь, ширина, высота)

    # --- Этап 1: Определение максимальной ширины и сбор данных ---
    print("Этап 1: Определение максимальной ширины...")
    for filename in image_files:
        img_path = os.path.join(folder_path, filename)
        try:
            with Image.open(img_path) as img:
                print(f"  - Проверено {filename}: ширина={img.width}, высота={img.height}")
                if img.width > max_width:
                    max_width = img.width
                images_data.append({'path': img_path, 'width': img.width, 'height': img.height})
        except Exception as e:
            print(f"Ошибка открытия или чтения размеров изображения {filename}: {e}")
            continue # Пропускаем поврежденные или нечитаемые файлы

    if not images_data:
        print("Не удалось обработать ни одного изображения.")
        return

    print(f"-> Максимальная ширина определена: {max_width} пикселей")

    # --- Этап 2: Расчет итоговой высоты с учетом масштабирования ---
    print("Этап 2: Расчет итоговой высоты...")
    actual_total_height = 0
    processed_image_info = [] # Список для хранения информации для вставки: (путь, целевая_ширина, целевая_высота)
    for data in images_data:
        original_width = data['width']
        original_height = data['height']
        target_width = max_width # Все изображения будут этой ширины
        target_height = original_height

        if original_width < max_width:
            # Рассчитываем новую высоту, сохраняя пропорции
            ratio = max_width / original_width
            target_height = int(original_height * ratio)
            print(f"  - Изображение {os.path.basename(data['path'])} будет масштабировано до {target_width}x{target_height}")
        else:
            # Если изображение шире или равно max_width, оно будет масштабировано до max_width
            # (или оставлено как есть, если равно). Высота изменится пропорционально.
            if original_width > max_width:
                 ratio = max_width / original_width
                 target_height = int(original_height * ratio)
                 print(f"  - Изображение {os.path.basename(data['path'])} будет уменьшено до {target_width}x{target_height}")
            else:
                 # Ширина равна max_width, высота не меняется
                 target_height = original_height
                 print(f"  - Изображение {os.path.basename(data['path'])} имеет нужную ширину {target_width}x{target_height}")

        actual_total_height += target_height
        processed_image_info.append({'path': data['path'], 'target_width': target_width, 'target_height': target_height})

    print(f"-> Итоговая расчетная высота: {actual_total_height} пикселей")

    # --- Этап 3: Создание холста и вставка изображений ---
    print("Этап 3: Создание холста и вставка изображений...")
    try:
        stitched_image = Image.new('RGB', (max_width, actual_total_height), (255, 255, 255))
    except Exception as e:
        print(f"Ошибка создания холста ({max_width}x{actual_total_height}): {e}")
        return

    current_y = 0
    for info in processed_image_info:
        img_path = info['path']
        target_width = info['target_width']
        target_height = info['target_height']
        try:
            with Image.open(img_path) as img:
                # Масштабируем, если необходимо (ширина не равна target_width или высота не равна target_height)
                if img.width != target_width or img.height != target_height:
                    print(f"  - Масштабирование {os.path.basename(img_path)} до {target_width}x{target_height}")
                    img_resized = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                    stitched_image.paste(img_resized, (0, current_y))
                    img_resized.close() # Закрываем измененное изображение
                else:
                    # Вставляем оригинал без масштабирования
                    print(f"  - Вставка {os.path.basename(img_path)} (оригинал)")
                    stitched_image.paste(img, (0, current_y))

                current_y += target_height # Смещаем Y на высоту вставленного изображения

        except Exception as e:
            print(f"Ошибка обработки/вставки изображения {os.path.basename(img_path)}: {e}")
            # Можно добавить логику пропуска или остановки
            continue

    # --- Этап 4: Сохранение результата ---
    print("Этап 4: Сохранение результата...")
    stitched_filename = f"stitched_{os.path.basename(folder_path)}.jpg"
    stitched_save_path = os.path.join(os.path.dirname(folder_path), stitched_filename)
    try:
        stitched_image.save(stitched_save_path, 'JPEG', quality=90)
        print(f"-> Склеенное изображение сохранено: {stitched_save_path}")
    except Exception as e:
        print(f"Ошибка сохранения склеенного изображения: {e}")
    finally:
        stitched_image.close()

def run_scraping(urls, save_directory):
    """Запускает процесс загрузки и склеивания изображений."""
    if not urls:
        print("Список URL пуст.")
        return

    if not save_directory:
        print("Папка для сохранения не выбрана.")
        return

    os.makedirs(save_directory, exist_ok=True)

    # Шаг 1: Загрузка изображений
    print("Начало загрузки изображений...")
    for url in urls:
        download_images(url, save_directory)

    print("\nЗагрузка изображений завершена.")

    # Шаг 2: Склеивание изображений
    print("\nНачало склеивания изображений...")
    all_subdirs = [os.path.join(save_directory, item) for item in os.listdir(save_directory) if os.path.isdir(os.path.join(save_directory, item))]

    if not all_subdirs:
        print("Не найдено папок с загруженными изображениями для склеивания.")
        return

    for item_path in all_subdirs:
        stitch_images(item_path)

    print("\nСклеивание изображений завершено.")

# Блок if __name__ == "__main__" удален, чтобы скрипт можно было импортировать