import os
import re
from datetime import datetime
from hashlib import sha256

from bs4 import BeautifulSoup
from pysummarization.abstractabledoc.top_n_rank_abstractor import TopNRankAbstractor
from pysummarization.nlpbase.auto_abstractor import AutoAbstractor
from pysummarization.tokenizabledoc.simple_tokenizer import SimpleTokenizer
from scrapy_redis.pipelines import RedisPipeline

from .es7 import ES7
from .support import TorHelper


class TorspiderPipeline(RedisPipeline):

    def __init__(self, server):
        super().__init__(server)
        self.dirname = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.helper = TorHelper()
        self.date = datetime.today()
        self.es = ES7()

    def process_item(self, item, spider):
        url = item["url"]
        domain = item['domain']
        page = item['page']

        btc_addr_pat = re.compile(
            r"\b(1[a-km-zA-HJ-NP-Z1-9]{25,34})\b|\b(3[a-km-zA-HJ-NP-Z1-9]{25,34})\b|\b(bc1[a-zA-HJ-NP-Z0-9]{25,39})\b"
        )
        addr_list = set()
        for res in btc_addr_pat.findall(page):
            addr_list.update(set(res))

        addr_list = set(filter(self.helper.check_bc, addr_list))
        url_hash = sha256(url.encode("utf-8")).hexdigest()

        soup = BeautifulSoup(page, "lxml")
        for s in soup.select('script'):
            s.decompose()
        for s in soup.select('style'):
            s.decompose()

        # Object of automatic summarization.
        auto_abstractor = AutoAbstractor()
        # Set tokenizer.
        auto_abstractor.tokenizable_doc = SimpleTokenizer()
        # Set delimiter for making a list of sentence.
        auto_abstractor.delimiter_list = [".", "\n"]
        # Object of abstracting and filtering document.
        abstractable_doc = TopNRankAbstractor()
        # Summarize document.
        result_dict = auto_abstractor.summarize(soup.getText(), abstractable_doc)

        summary = ""
        for sentence in result_dict["summarize_result"]:
            summary = summary + sentence.strip()

        tag = {
            "timestamp": datetime.now().timestamp() * 1000,
            "type": "service",
            "source": "tor",
            "method": "html",
            "info": {
                "domain": domain,
                "url": url,
                "title": item['title'],
                "external_urls": {
                    "href_urls": {
                        "web": item["external_links_web"],
                        "tor": item["external_links_tor"]
                    }
                },
                "tags": {
                    "cryptocurrency": {
                        "address": {
                            "btc": list(addr_list)
                        }
                    },
                    "hidden_service": {
                        "landing_page": item["is_landing_page"]
                    }
                }
            },
            "summary": summary
        }

        try:
            self.write_to_file(page, url_hash)
        except:
            pass

        self.es.persist_report(tag, url_hash)

    def write_to_file(self, page, es_id):
        current_date = datetime.today()
        if self.date != current_date:
            self.date = current_date
            try:
                os.makedirs("/mnt/data/" + self.date.strftime("%d-%m-%y"))
            except OSError:
                pass

        f = open("/mnt/data/{date}/{id}".format(date=self.date.strftime("%d-%m-%y"), id=es_id), "w")
        f.write(page)
        f.close()
