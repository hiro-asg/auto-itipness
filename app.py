import sys
import re
import yaml
import time
from datetime import datetime, timedelta, timezone
from logging import basicConfig, getLogger, DEBUG
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from bs4 import BeautifulSoup

logger = getLogger(__name__)
logger.setLevel(DEBUG)
JST = timezone(timedelta(hours=+9), 'JST')

class WebDriver(object):

    def main(self, url, propaties):
        options = Options()
        options.add_argument("--headless")
        try:
            driver = webdriver.Chrome("/home/ec2-user/environment/chromedriver", chrome_options=options)
            driver.get(url + "/i/user/")
        except Exception as e:
            logger.exception(e)

        try:
            input_email = driver.find_element_by_name("login_id")
            input_pass = driver.find_element_by_name("login_pass")
            input_email.send_keys(propaties["email"])
            input_pass.send_keys(str(propaties["pass"]))
            self.takeScreenshot(driver)
            driver.find_element_by_class_name("btnEmail").click()
            
            #検索画面表示
            driver.get(url + "/i/program/search")
            if "studioclosed" in driver.current_url:
               logger.info("メンテナンス中のため終了します。")
               driver.quit()
               raise SystemMaintenanceException

            #料金（無料のみ）
            input_fee = Select(driver.find_element_by_id("f_fee"))
            input_fee.select_by_visible_text("無料のみ")

            bs = BeautifulSoup(driver.page_source, 'html.parser')
            check_box_groups = bs.find_all("ul", {"class":"checkListInline"})
            shop_list = check_box_groups[0]
            day_list = check_box_groups[1]
            
            #店舗
            if shop_list:
                for shop in shop_list.find_all("li"):
                    check_box = driver.find_element_by_id(shop.input["id"])
                    if check_box.get_attribute("checked") and not any(s for s in propaties["shop"] if s in shop.find("label").text):
                        check_box.click()
                    elif not check_box.get_attribute("checked") and any(s for s in propaties["shop"] if s in shop.find("label").text):
                        check_box.click()
                        
            #曜日
            if day_list:
                for day in day_list.find_all("li"):
                    check_box = driver.find_element_by_id(day.input["id"])
                    if check_box.get_attribute("checked") and not any(s for s in propaties["day"] if s in day.find("label").text):
                        check_box.click()
                    elif not check_box.get_attribute("checked") and any(s for s in propaties["day"] if s in day.find("label").text):
                        check_box.click()
                        
            #ご利用希望日
            trg_date = (datetime.now(JST) + timedelta(days=10)).strftime("%Y/%m/%d")
            input_start = Select(driver.find_element_by_name("start_date"))
            input_end = Select(driver.find_element_by_name("end_date"))
            input_start.select_by_value(trg_date)
            input_end.select_by_value(trg_date)
            
            #開始時間帯
            input_hour = Select(driver.find_element_by_id("s_hour"))
            input_hour.select_by_value((str(propaties["hour"]).zfill(2) if int(propaties["hour"]) > 8 else "00")  + "-" + str(propaties["hour"]))
            
            #プログラム名
            input_program = driver.find_element_by_id("name")
            input_program.clear()
            if propaties["program"]:
                input_program.send_keys(propaties["program"])
            
            #インストラクター名
            input_instructor = driver.find_element_by_id("instructor")
            input_instructor.clear()
            if propaties["instructor"]:
                input_instructor.send_keys(propaties["instructor"])
            
            #検索実行
            self.takeScreenshot(driver)
            driver.find_element_by_class_name("btn").click()
            
            #予約実行
            bs = BeautifulSoup(driver.page_source, 'html.parser')
            reservation_link = bs.find("a", text="予約する")
            if reservation_link:
                #予約確認ページへ遷移
                self.takeScreenshot(driver)
                driver.get(url + reservation_link["href"])
                
                #メール通知をONにし、パスワードを入力して予約確定
                driver.find_element_by_id("email").click()
                driver.find_element_by_name("password").send_keys(propaties["pass"])
                self.takeScreenshot(driver)
                driver.find_element_by_class_name("btn").click()
                
                bs = BeautifulSoup(driver.page_source, 'html.parser')
                reservation_link = bs.find("div", text=re.compile("予約完了"))
                if reservation_link:
                    logger.info("レッスンの予約が完了しました。")
                else:
                    logger.warn("何らかの理由によりレッスンの予約ができませんでした。")
                self.takeScreenshot(driver)
            else:
                logger.nfo("予約可能なレッスンがありませんでした。") 
                self.takeScreenshot(driver)
               
        except NoSuchElementException as e:
            logger.error("サイトのレイアウトが変更された可能性があります。" + e)
            self.takeScreenshot(driver)
        except Exception as e:
            logger.exception(e)
            self.takeScreenshot(driver)
            
        driver.quit()

    def takeScreenshot(self, driver):
        page_width = driver.execute_script("return document.body.scrollWidth")
        page_height = driver.execute_script("return document.body.scrollHeight")
        driver.set_window_size(page_width, page_height)
        driver.save_screenshot("screenshots/" + datetime.now(JST).strftime("%Y-%m-%d-%H%M%S" + ".png"))

class SystemMaintenanceException(Exception):
    pass

if __name__ == "__main__":
    f = open("app.yml", "r+")
    wd = WebDriver()
    maintenance_wait_count = 0
    while maintenance_wait_count < 10:
        try:
            wd.main("https://i.tipness.co.jp", yaml.load(f))
            sys.exit()
        except SystemMaintenanceException as e:
            maintenance_wait_count += 1
            time.sleep(60)
    logger.warn("メンテナンス時間が10分以上経過したため処理を中断します。")
    sys.exit()
