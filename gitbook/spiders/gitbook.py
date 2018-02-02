import queue
import threading

import scrapy
from selenium import webdriver
import json, base64

from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import selenium.webdriver.chrome.service as chrome_service

# 需要保存pdf的gitbook地址
gitbook_url = 'https://kubernetes.feisky.xyz'
# 临时存放单个页面pdf的目录
gitbook_tmppdf_dir = '.'
# 最多同时开启多少个打印到pdf实例
max_printer = 10

def send_devtools(driver, cmd, params={}):
    resource = "/session/%s/chromium/send_command_and_get_result" % driver.session_id
    url = driver.command_executor._url + resource
    body = json.dumps({'cmd': cmd, 'params': params})
    response = driver.command_executor._request('POST', url, body)
    if response['status']:
        raise Exception(response.get('value'))
    return response.get('value')

def save_as_pdf(driver, path, options={}):
    # https://timvdlippe.github.io/devtools-protocol/tot/Page#method-printToPDF
    result = send_devtools(driver, "Page.printToPDF", options)
    with open(path, 'wb') as file:
        file.write(base64.b64decode(result['data']))

def save_pdf(driver,url,output):
    try:
        driver.get(url)
        WebDriverWait(driver, 3600).until(
            EC.presence_of_element_located((By.CLASS_NAME, "pull-left"))
        )
        driver.maximize_window()
        # pull_left.click()
        driver.execute_script("""
            (function(){
                var scip = document.createElement("script");

                newatt=scip.setAttribute("src","https://cdn.bootcss.com/jquery/3.2.1/jquery.min.js");
                newatt=scip.setAttribute("type","text/javascript");
                newatt=scip.setAttribute("charset","utf-8");

                x=document.getElementsByTagName("head")[0];
                x.appendChild(scip);
                $(".pull-left")[0].click()
                $(".navigation-next,.navigation-prev,.book-header,.page-footer,.gitbook-donate,.treeview__container").each(function(){
                    $(this).remove();
                });
                $("#disqus_thread").each(function(){
                    $(this).remove();
                });
                $(".book-body").css("position","static");

            })()
        """)

        out = '%s.pdf' % (output)
        print("start to write %s"%(out))
        save_as_pdf(driver, out, {'landscape': False})
    finally:
        driver.close()


# scrapy crawl gitbook 2>&1 | grep "^{" | grep "'text'" | grep "'href'"
class QuotesSpider(scrapy.Spider):
    name = "gitbook"
    start_urls = [ gitbook_url]

    def __init__(self):
        print("init")

        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")


        service = chrome_service.Service("chromedriver")
        service.start()
        self.service = service
        self.capabilities = options.to_capabilities()
        # ---
        # self.driver = webdriver.Remote(
        #     command_executor='http://192.168.1.160:4444/wd/hub',
        #     desired_capabilities=options.to_capabilities()
        # )

        self.q = queue.Queue()
        self.exit_flag = False
        self.driver_mutex = threading.Lock()
        self.max_thread = max_printer
        self.threads_array = []

        for i in range(self.max_thread):
            thread = threading.Thread(target=self.c)
            thread.start()
            self.threads_array.append(thread)

    def c(self):
        while True:
            if self.exit_flag:
                break
            try:
                element = self.q.get(timeout=1)
            except:
                continue
            if element is None:
                return

            print("start to thread %s"%(element["file"]))
            self.q.task_done()

            self.driver_mutex.acquire()
            driver = webdriver.Remote(
                self.service.service_url,
                desired_capabilities=self.capabilities
            )
            self.driver_mutex.release()
            save_pdf(driver, element["url"], element["file"])
            print("end to thread %s"%(element["file"]))

    def parse_hierarchy(self, response, parents, count, prefix):
        for chapter in parents:
            text = chapter.xpath('./a//text()').extract()
            text = ''.join([i.strip() for i in text])
            href = chapter.css('a').xpath('@href').extract_first()
            if text and href:
                text = text.strip()
                url = response.urljoin(href.strip())
                self_prefix = "%s_%d"%(prefix,count)
                # print("start to save [%s]%s from %s"%(self_prefix,text,url))
                print("[%s]%s"%(self_prefix,text))

                self.q.put({
                    "url": url,
                    "file": "%s/[%s]%s"%(gitbook_tmppdf_dir,self_prefix,text),
                })

                count += 1

                sub_parents = chapter.xpath('./ul/li[contains(@class,"chapter")]')
                if len(sub_parents) > 0:
                    count = self.parse_hierarchy(response,sub_parents,count, self_prefix)
        return count

    def parse(self, response):
        print("start")

        count = self.parse_hierarchy(
            response,
            response.xpath('//nav/ul/li[contains(@class,"chapter")]'),
            1,
            "")

        print("done1 %d"%(count))
        self.q.join()
        self.exit_flag = True
        print("done")
        for thread in self.threads_array:
            thread.join()


