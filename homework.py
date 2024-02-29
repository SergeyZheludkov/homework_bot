from dotenv import load_dotenv
import logging
import os
import requests
import sys
import telegram
import time

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

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
    for token in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
        if token is None:
            return False
    return True


def send_message(bot, message):
    """Delivery message to Telegram chat."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug('Сообщение направлено в Telegram')
    except Exception as error:
        logging.error(f'Сбой при отправке сообщения в Telegram. {error}')


def get_api_answer(timestamp):
    """Request to API-service practicum.yandex."""
    try:
        response = requests.get(ENDPOINT, headers=HEADERS,
                                params={'from_date': timestamp})
        status_code = response.status_code
        if status_code != 200:
            logging.error(f'Недоступность эндпойнта {ENDPOINT}. '
                          'Статус {status_code}')
            raise RuntimeError
        return response.json()
    except requests.RequestException:
        logging.error(f'Недоступность эндпойнта {ENDPOINT}')
        raise RuntimeError
    except Exception as error:
        logging.error(f'Ошибка в функции get_api_answer: {error}')
        raise RuntimeError


def check_response(response):
    """Check response structure and type of values."""
    # Проверка наличия необходимых ключей.
    for key in ('homeworks', 'current_date'):
        if key not in response:
            message = f'Ключа {key} нет в ответе API.'
            logging.error(message)
            raise TypeError(message)

    # Проверка соответствия типов данных ожидаемым типам.
    if not (isinstance(response.get('homeworks'), list) and isinstance(
            response.get('current_date'), int
    )):
        message = 'Неверный тип значения ключа в ответе API'
        logging.error(message)
        raise TypeError(message)


def check_response_send_message(response, bot, count):
    """Check response and send message to Telegram in case of first error."""
    try:
        check_response(response)
    except TypeError as error:
        # Если ошибка в функции в первый раз,
        # то направляем сообщение в Telegram.
        if count == 0:
            send_message(bot, str(error))
        count += 1
    finally:
        return count


def parse_status(homework):
    """Get details of the latest homework."""
    # Проверка наличия необходимых ключей.
    for key in ('homework_name', 'status'):
        if key not in homework:
            message = f'Ключ {key} не обнаружен в информации о домашке.'
            logging.error(message)
            raise KeyError(message)

    homework_name = homework.get('homework_name')
    status = homework.get('status')

    # Проверка соответствия статуса домашки ряду стандартных вариантов.
    if status not in HOMEWORK_VERDICTS:
        message = 'Нестандартный статус в информации о домашке.'
        logging.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS.get(status)
    return (f'Изменился статус проверки работы "{homework_name}". {verdict}')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Не хватает переменных окружения. '
                         'Без них бот не будет работать.')
        exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    #  Счетчик ошибок в функции check_response.
    count_cr = 0

    #  Счетчик ошибок в функции parse_status.
    count_ps = 0

    while True:
        try:
            timestamp = int(time.time() - RETRY_PERIOD)
            response = get_api_answer(timestamp)
            count_cr = check_response_send_message(response, bot, count_cr)

            if len(response.get('homeworks')) != 0:
                try:
                    message = parse_status(response.get('homeworks')[0])
                    send_message(bot, message)
                except KeyError as error:
                    # Если ошибка в функции в первый раз,
                    # то направляем сообщение в Telegram.
                    if count_ps == 0:
                        send_message(bot, str(error))
                    count_ps += 1
            else:
                logging.debug('В ответе API нет новых статусов.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.critical(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
