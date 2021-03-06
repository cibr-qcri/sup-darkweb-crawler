from elasticsearch import Elasticsearch
from scrapy.utils.project import get_project_settings

from .singleton import Singleton


class ES7(metaclass=Singleton):

    def __init__(self):
        self.settings = get_project_settings()
        self.server = self.settings['ELASTICSEARCH_CLIENT_SERVICE_HOST']
        self.port = self.settings['ELASTICSEARCH_CLIENT_SERVICE_PORT']
        self.port = int(self.port)
        self.username = self.settings['ELASTICSEARCH_USERNAME']
        self.password = self.settings['ELASTICSEARCH_PASSWORD']
        self.index = self.settings['ELASTICSEARCH_INDEX']

        if self.port:
            uri = "http://%s:%s@%s:%d" % (self.username, self.password, self.server, self.port)
        else:
            uri = "http://%s:%s@%s" % (self.username, self.password, self.server)
        self.es = Elasticsearch([uri], retry_on_timeout=True)

    @staticmethod
    def unify(url):
        if not url:
            return ""
        if url.startswith("http://") or url.startswith("https://"):
            pass
        else:
            url = "http://" + url
        return url.strip("/")

    def get_domains(self):
        aggs = {
            "domains": {
                "terms": {
                    "field": "info.domain", "size": 50000
                }
            }
        }

        res = self.es.search(index="crawlers_v2", body={
            "size": 0,
            "aggs": aggs,
        })

        results = [domain['key'] for domain in res['aggregations']['domains']['buckets']]
        return results

    def persist_report(self, report, es_id):
        self.es.index(index=self.index, id=es_id, body=report)
