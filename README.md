### HCSpider
A generic spider for security testing. The built-in spiders in common scanning tools crawl all the links to the HTML file. This may seem like a very comprehensive way, but it is incomplete and inefficient for security testing. Many web pages use js or ajax to dynamically generate page content. The urls in these content cannot be obtained through some library like requests. In addition, the content of many pages is generated by the frameworks. For example, the display of merchandise, the playing page of video, etc., except for the content, the logic is exactly the same. For security testing, we don't need to crawl and test those same pages.

Our spider use `selenium` + `headless chrome` to simulate a real browser environment and parse url in both static and dynamic content. We use the bloom filter and the url path similarity to clean the duplicate content.

### Usage
When you install all relevant dependencies, you can use start spider easily like this:

```
start_spider('https://www.example.com', domain=REG_DOMAIN, deep=0, delay_level=3, method='get', data=None, cookie='a=1;b=3')

    surl        strat url: "https://www.baidu.com/?a=1&b=2" / scheme is required
    domain      domain scope      [default = *]
    deep        recursion depth   [default = 0]
    delay_level delay crawl level [default = 0] / scope:0-5
    method      support get/post in lowercase [default = get]
    data        post method parmas [default = None]
    cookie      you can copy the chrome cookies field directly, we will parse it [default = None]
```
In addition to these parameters, there are some other fields that need attention, you need to change them according to your situation:

```
MAX_RECURSION_DEPTH     The maximum depth relative to the root node
url_bloom               BloomFilter accuracy
DB_CONNECT_STRING       Your database config
DEFAULT_THREAD_NUMBER   The number of threads
```
