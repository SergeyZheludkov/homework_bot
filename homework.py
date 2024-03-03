from dotenv import load_dotenv
from http import HTTPStatus
import logging
import os
import requests
import sys
import telegram
import time

from exceptions import (APIRequestError, CheckResponseError,
                        ParseError, SendMessageError)

# logging.basicConfig(level=logging.DEBUG,
#                     format='%(asctime)s [%(levelname)s] %(message)s')

# Создаем отдельный логгер для модуля
logger = logging.getLogger(__name__)

# Устанавливаем уровень DEBUG, с которого логи будут выводиться
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')

# ВЫбираем обработчик логов StreamHandler с выводом в поток sys.stdout.
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

# Применяем форматтер к хэндлеру
handler.setFormatter(formatter)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Период повторной попытки запроса, в сек.
RETRY_PERIOD = 600

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Check neccessary tokens are available from environment."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for name in ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID'):
        if tokens[name] is None:
            logger.critical(f'Не хватает переменной окружения {name}. '
                            'Без нее бот не будет работать.')
            return False
    return True


def send_message(bot, message):
    """Delivery message to Telegram chat."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        raise SendMessageError
    logger.debug('Сообщение направлено в Telegram')


def get_api_answer(timestamp):
    """Request to API-service practicum.yandex."""
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params={'from_date': timestamp})
    except requests.RequestException:
        raise APIRequestError(f'Недоступность эндпойнта {ENDPOINT}')
    except Exception as error:
        raise APIRequestError(f'Ошибка в функции get_api_answer: {error}')
    else:
        status_code = response.status_code
        if status_code != HTTPStatus.OK:
            raise APIRequestError(f'Недоступность эндпойнта {ENDPOINT}. '
                                  f'Статус {status_code}')

    return response.json()


def check_response(response):
    """Check response structure and type of values."""
    # Проверка наличия необходимых ключей.
    for homeworks_key in ('homeworks', 'current_date'):
        if homeworks_key not in response:
            message = f'ключа {homeworks_key} нет в ответе API.'
            raise CheckResponseError(message)

    # Проверка соответствия типов данных ожидаемым типам.
    if not (isinstance(response.get('homeworks'), list) and isinstance(
            response.get('current_date'), int
    )):
        message = 'неверный тип значения ключа в ответе API'
        raise CheckResponseError(message)


def parse_status(homework):
    """Get details of the latest homework."""
    # Проверка наличия необходимых ключей.
    for homework_key in ('homework_name', 'status'):
        if homework_key not in homework:
            message = f'ключ {homework_key} не обнаружен'
            raise ParseError(message)

    homework_name = homework.get('homework_name')
    status = homework.get('status')

    # Проверка соответствия статуса домашки ряду стандартных вариантов.
    if status not in HOMEWORK_VERDICTS:
        message = 'нестандартный статус в информации о домашке.'
        raise ParseError(message)

    verdict = HOMEWORK_VERDICTS.get(status)
    return (f'Изменился статус проверки работы "{homework_name}". '
            f'{verdict}')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    timestamp = int(time.time())

    while True:
        error_message = ''
        sent_message_flag = True
        try:
            response_content = get_api_answer(timestamp)
            check_response(response_content)
            timestamp = response_content.get('current_date')
            homeworks = response_content.get('homeworks')
            if homeworks:
                for homework in homeworks:
                    status_message = parse_status(homework)
                    send_message(bot, status_message)
            else:
                logger.debug('В ответе API нет новых статусов.')
        except SendMessageError:
            error_message = 'Сбой при отправке сообщения в Telegram'
            sent_message_flag = False
        except CheckResponseError as error:
            error_message = f'Сбой при проверке ответа API: {error}'
        except ParseError as error:
            error_message = f'Сбой при извлечении данных по домашке: {error}'
        except Exception as error:
            error_message = f'Сбой в работе программы: {error}'
        finally:
            if error_message:
                logger.error(error_message)
                if sent_message_flag:
                    send_message(bot, error_message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
