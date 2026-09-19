# Golden 首批 20 题审核包

日期：2026-09-16。状态：**AI 预审，尚无人审核；未写入 Golden 或审核进度。**

本批为 cand-basic-001 至 020。所有题目都包含文件哈希和宽泛的章节提问，建议先改为自然、具体问题；原题保留在下方供核对。标注不是人工结论。

操作：回复“001 修改：……；002 拒绝；……”并提供真实审核人标识。不要整体接受本批。修改后的题目会再次展示确认，不会自动视为通过。

证据来自当前本地语料快照，不代表外部文档最新状态。摘录仅用于定位；链接和 Markdown 标记会造成逐字匹配失败，不能据此断言无证据。应点开完整来源复核。

## 001 · cand-basic-001

- 原问题：What is covered in the documentation section 'Body - Updates¶ (0165ea5581ca25021aaec7297c2cc0bbcc6f232415f4dfd62afc25da270dfe49)'?
- 原预期答案：To update an item you can use the HTTP PUT operation.
- AI 预审：建议将章节概述改为具体知识问题，去掉文件哈希；答案支持范围需人工确认。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/0165ea5581ca25021aaec7297c2cc0bbcc6f232415f4dfd62afc25da270dfe49.md)

来源摘录（最多 700 字符，可能截断）：

> # Body - Updates[¶](#body-updates)
> 
> ## Update replacing with `PUT`[¶](#update-replacing-with-put)
> 
> To update an item you can use the [HTTP `PUT`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/PUT) operation.
> 
> You can use the `jsonable_encoder` to convert the input data to data that can be stored as JSON (e.g. with a NoSQL database). For example, converting `datetime` to `str`.
> 
> ```
> from fastapi import FastAPI
> from fastapi.encoders import jsonable_encoder
> from pydantic import BaseModel
> app = FastAPI()
> class Item(BaseModel):
> name: str | None = None
> description: str | None = None
> price: float | None = None
> tax: float = 10.5
> tags: list[str] = []
> items = {
> "foo": {

## 002 · cand-basic-002

- 原问题：What is covered in the documentation section 'Testing¶ (046c3b78e43555331414b5214344987bc3e42e53b0f1f48ffb408b699d895e77)'?
- 原预期答案：Thanks to Starlette, testing FastAPI applications is easy and enjoyable.
- AI 预审：答案是宣传性评价，建议改成如何使用 TestClient 并补充操作步骤。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/046c3b78e43555331414b5214344987bc3e42e53b0f1f48ffb408b699d895e77.md)

来源摘录（最多 700 字符，可能截断）：

> # Testing[¶](#testing)
> 
> Thanks to [Starlette](https://starlette.dev/testclient/), testing **FastAPI** applications is easy and enjoyable.
> 
> It is based on [HTTPX](https://www.python-httpx.org), which in turn is designed based on Requests, so it's very familiar and intuitive.
> 
> With it, you can use [pytest](https://docs.pytest.org/) directly with **FastAPI**.
> 
> ## Using `TestClient`[¶](#using-testclient)
> 
> Import `TestClient`.
> 
> Create a `TestClient` by passing your **FastAPI** application to it.
> 
> Create functions with a name that starts with `test_` (this is a standard `pytest` convention).
> 
> Use the `TestClient` object the same way as you do with `httpx`.
> 
> Write simple `assert` 

## 003 · cand-basic-003

- 原问题：What is covered in the documentation section 'Form Models¶ (059295d9af32905b98bebe159fd841744da5f716a32088512b0d2becf002ba56)'?
- 原预期答案：You can use Pydantic models to declare form fields in FastAPI.
- AI 预审：建议将章节概述改为具体知识问题，去掉文件哈希；答案支持范围需人工确认。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/059295d9af32905b98bebe159fd841744da5f716a32088512b0d2becf002ba56.md)

来源摘录（最多 700 字符，可能截断）：

>  inputs are not permitted",
> "input": "Mr. Poopybutthole"
> }
> ]
> }
> ```
> ## Summary[¶](#summary)
> 
> You can use Pydantic models to declare form fields in FastAPI. 😎

## 004 · cand-basic-004

- 原问题：What is covered in the documentation section 'Deploy FastAPI on Cloud Providers¶ (0b6e930cbeded1fbc252c989cf392156267d06094c284cf9bd5f9fb63fef2dea)'?
- 原预期答案：You can use virtually any cloud provider to deploy your FastAPI application.
- AI 预审：建议将章节概述改为具体知识问题，去掉文件哈希；答案支持范围需人工确认。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/0b6e930cbeded1fbc252c989cf392156267d06094c284cf9bd5f9fb63fef2dea.md)

来源摘录（最多 700 字符，可能截断）：

> # Deploy FastAPI on Cloud Providers[¶](#deploy-fastapi-on-cloud-providers)
> 
> You can use virtually **any cloud provider** to deploy your FastAPI application.
> 
> In most of the cases, the main cloud providers have guides to deploy FastAPI with them.
> 
> ## FastAPI Cloud[¶](#fastapi-cloud)
> 
> **[FastAPI Cloud](https://fastapicloud.com)** is built by the same author and team behind **FastAPI**.
> 
> It streamlines the process of **building**, **deploying**, and **accessing** an API with minimal effort.
> 
> It brings the same **developer experience** of building apps with FastAPI to **deploying** them to the cloud. 🎉
> 
> FastAPI Cloud is the primary sponsor and funding provider for the *FastAPI and

## 005 · cand-basic-005

- 原问题：What is covered in the documentation section 'WebSockets¶ (0be2b9eb00086821e866264b11a7aef2add21a51f7a31a57695cc91facea85d5)'?
- 原预期答案：Add websockets (a Python library that makes it easy to use the "WebSocket" protocol) to your project:
- AI 预审：答案以冒号结束，是安装引导而非完整答案；需补齐具体操作。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/0be2b9eb00086821e866264b11a7aef2add21a51f7a31a57695cc91facea85d5.md)

来源摘录（最多 700 字符，可能截断）：

> # WebSockets[¶](#websockets)
> 
> You can use [WebSockets](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API) with **FastAPI**.
> 
> ## Install `websockets`[¶](#install-websockets)
> 
> Add `websockets` (a Python library that makes it easy to use the "WebSocket" protocol) to your project:
> 
> ```
> $ uv add websockets
> ---> 100%
> ```
> ## WebSockets client[¶](#websockets-client)
> 
> ### In production[¶](#in-production)
> 
> In your production system, you probably have a frontend created with a modern framework like React, Vue.js or Angular.
> 
> And to communicate using WebSockets with your backend you would probably use your frontend's utilities.
> 
> Or you might have a native mobile applica

## 006 · cand-basic-006

- 原问题：What is covered in the documentation section 'CORS (Cross-Origin Resource Sharing)¶ (111ea56d80c75510a9e43cb22fc497e7b0acc47050d0421708f01fcd4b7cc71d)'?
- 原预期答案：CORS or "Cross-Origin Resource Sharing" refers to the situations when a frontend running in a browser has JavaScript code that communicates with a backend, and the backend is in a different "origin" than the frontend.
- AI 预审：建议将章节概述改为具体知识问题，去掉文件哈希；答案支持范围需人工确认。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/111ea56d80c75510a9e43cb22fc497e7b0acc47050d0421708f01fcd4b7cc71d.md)

来源摘录（最多 700 字符，可能截断）：

> # CORS (Cross-Origin Resource Sharing)[¶](#cors-cross-origin-resource-sharing)
> 
> [CORS or "Cross-Origin Resource Sharing"](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS) refers to the situations when a frontend running in a browser has JavaScript code that communicates with a backend, and the backend is in a different "origin" than the frontend.
> 
> ## Origin[¶](#origin)
> 
> An origin is the combination of protocol (`http`, `https`), domain (`myapp.com`, `localhost`, `localhost.tiangolo.com`), and port (`80`, `443`, `8080`).
> 
> So, all these are different origins:
> 
> - `http://localhost`
> - `https://localhost`
> - `http://localhost:8080`
> 
> Even if they are all in `localhost`, they us

## 007 · cand-basic-007

- 原问题：What is covered in the documentation section 'Templates¶ (1470b4b765dbd909cda1424bdff408c8580b302ff8b0633b6dc874f9e573285f)'?
- 原预期答案：You can use any template engine you want with FastAPI.
- AI 预审：建议将章节概述改为具体知识问题，去掉文件哈希；答案支持范围需人工确认。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/1470b4b765dbd909cda1424bdff408c8580b302ff8b0633b6dc874f9e573285f.md)

来源摘录（最多 700 字符，可能截断）：

> # Templates[¶](#templates)
> 
> You can use any template engine you want with **FastAPI**.
> 
> A common choice is Jinja2, the same one used by Flask and other tools.
> 
> There are utilities to configure it easily that you can use directly in your **FastAPI** application (provided by Starlette).
> 
> ## Install dependencies[¶](#install-dependencies)
> 
> Add `jinja2` to your project:
> 
> ```
> $ uv add jinja2
> ---> 100%
> ```
> ## Using `Jinja2Templates`[¶](#using-jinja2templates)
> 
> - Import `Jinja2Templates` .
> - Create a `templates` object that you can reuse later.
> - Declare a `Request` parameter in the*path operation* that will return a template.
> - Use the `templates` you created to render and retu

## 008 · cand-basic-008

- 原问题：What is covered in the documentation section 'Behind a Proxy¶ (19c45d265abf20db23194eb83d94f7815b564eb3f0ae1a2cd0526643af1b8ddb)'?
- 原预期答案：In many situations, you would use a proxy like Traefik or Nginx in front of your FastAPI app.
- AI 预审：建议将章节概述改为具体知识问题，去掉文件哈希；答案支持范围需人工确认。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/19c45d265abf20db23194eb83d94f7815b564eb3f0ae1a2cd0526643af1b8ddb.md)

来源摘录（最多 700 字符，可能截断）：

> # Behind a Proxy[¶](#behind-a-proxy)
> 
> In many situations, you would use a **proxy** like Traefik or Nginx in front of your FastAPI app.
> 
> These proxies could handle HTTPS certificates and other things.
> 
> ## Proxy Forwarded Headers[¶](#proxy-forwarded-headers)
> 
> A **proxy** in front of your application would normally set some headers on the fly before sending the requests to your **server** to let the server know that the request was **forwarded** by the proxy, letting it know the original (public) URL, including the domain, that it is using HTTPS, etc.
> 
> The **server** program (for example **Uvicorn** via **FastAPI CLI**) is capable of interpreting these headers, and then passing that 

## 009 · cand-basic-009

- 原问题：What is covered in the documentation section 'Editor Support¶ (1ec773453618fa968ed3a1a79afaab95d866a679c1c828e7c9b2f5e9adef3c7d)'?
- 原预期答案：The official FastAPI Extension enhances your FastAPI development workflow with path operation discovery, navigation, as well as FastAPI Cloud deployment, and live log streaming.
- AI 预审：扩展功能与版本相关；问题需明确文档快照，避免当作永久事实。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/1ec773453618fa968ed3a1a79afaab95d866a679c1c828e7c9b2f5e9adef3c7d.md)

来源摘录（最多 700 字符，可能截断）：

> # Editor Support[¶](#editor-support)
> 
> The official [FastAPI Extension](https://marketplace.visualstudio.com/items?itemName=FastAPILabs.fastapi-vscode) enhances your FastAPI development workflow with *path operation* discovery, navigation, as well as FastAPI Cloud deployment, and live log streaming.
> 
> For more details about the extension, refer to the README on the [GitHub repository](https://github.com/fastapi/fastapi-vscode).
> 
> ## Setup and Installation[¶](#setup-and-installation)
> 
> The **FastAPI Extension** is available for both [VS Code](https://code.visualstudio.com/) and [Cursor](https://www.cursor.com/). It can be installed directly from the Extensions panel in each editor by sear

## 010 · cand-basic-010

- 原问题：What is covered in the documentation section 'FastAPI¶ (2145a293aafaea81a5a60adcb28c6e2f81ecf68d2da0f5fe6acb6b59c828ecb8)'?
- 原预期答案：FastAPI Conf '26 October 28, 2026 Amsterdam, NL All about FastAPI, right from the source. Learn more
- AI 预审：答案是大会宣传，不适合作为 FastAPI 核心技术题；建议替换。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/2145a293aafaea81a5a60adcb28c6e2f81ecf68d2da0f5fe6acb6b59c828ecb8.md)

来源摘录（最多 700 字符，可能截断）：

> [FastAPI Conf '26 October 28, 2026 Amsterdam, NL All about FastAPI, right from the source. Learn more](https://fastapiconf.com)
> 
> # FastAPI[¶](#fastapi)
> 
> *FastAPI framework, high performance, easy to learn, fast to code, ready for production*
> 
> **Documentation**: [https://fastapi.tiangolo.com](https://fastapi.tiangolo.com)
> 
> **Source Code**: [https://github.com/fastapi/fastapi](https://github.com/fastapi/fastapi)
> 
> FastAPI is a modern, fast (high-performance), web framework for building APIs with Python based on standard Python type hints.
> 
> The key features are:
> 
> - **Fast** : Very high performance, on par with**NodeJS** and**Go** (thanks to Starlette and Pydantic).[One of the faste

## 011 · cand-basic-011

- 原问题：What is covered in the documentation section 'Body - Nested Models¶ (251925bd15b1035568cf009f275a0455c14957a0fae244cd20d36f56fa2c2c0f)'?
- 原预期答案：With FastAPI, you can define, validate, document, and use arbitrarily deeply nested models (thanks to Pydantic).
- AI 预审：建议将章节概述改为具体知识问题，去掉文件哈希；答案支持范围需人工确认。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/251925bd15b1035568cf009f275a0455c14957a0fae244cd20d36f56fa2c2c0f.md)

来源摘录（最多 700 字符，可能截断）：

> # Body - Nested Models[¶](#body-nested-models)
> 
> With **FastAPI**, you can define, validate, document, and use arbitrarily deeply nested models (thanks to Pydantic).
> 
> ## List fields[¶](#list-fields)
> 
> You can define an attribute to be a subtype. For example, a Python `list`:
> 
> ```
> from fastapi import FastAPI
> from pydantic import BaseModel
> app = FastAPI()
> class Item(BaseModel):
> name: str
> description: str | None = None
> price: float
> tax: float | None = None
> tags: list = []
> @app.put("/items/{item_id}")
> async def update_item(item_id: int, item: Item):
> results = {"item_id": item_id, "item": item}
> return results
> ```
> This will make `tags` be a list, although it doesn't declare th

## 012 · cand-basic-012

- 原问题：What is covered in the documentation section 'Deployment¶ (253b111e6bfcaff74129620b3e2030db67fccbf243b40575da35bffa079c5472)'?
- 原预期答案：Deploying a FastAPI application is relatively easy.
- AI 预审：答案只有“部署较容易”，缺少可验证知识点；建议替换。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/253b111e6bfcaff74129620b3e2030db67fccbf243b40575da35bffa079c5472.md)

来源摘录（最多 700 字符，可能截断）：

> # Deployment[¶](#deployment)
> 
> Deploying a **FastAPI** application is relatively easy.
> 
> ## What Does Deployment Mean[¶](#what-does-deployment-mean)
> 
> To **deploy** an application means to perform the necessary steps to make it **available to the users**.
> 
> For a **web API**, it normally involves putting it in a **remote machine**, with a **server program** that provides good performance, stability, etc, so that your **users** can **access** the application efficiently and without interruptions or problems.
> 
> This is in contrast to the **development** stages, where you are constantly changing the code, breaking it and fixing it, stopping and restarting the development server, etc.
> 
> ##

## 013 · cand-basic-013

- 原问题：What is covered in the documentation section 'Request Files¶ (26a0b3efffe80a9aefaa5cc7b110757ce416de1b991bdde00bf1f68dec405249)'?
- 原预期答案：You can define files to be uploaded by the client using File.
- AI 预审：建议将章节概述改为具体知识问题，去掉文件哈希；答案支持范围需人工确认。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/26a0b3efffe80a9aefaa5cc7b110757ce416de1b991bdde00bf1f68dec405249.md)

来源摘录（最多 700 字符，可能截断）：

> # Request Files[¶](#request-files)
> 
> You can define files to be uploaded by the client using `File`.
> 
> Note
> 
> To receive uploaded files, first install [`python-multipart`](https://github.com/Kludex/python-multipart).
> 
> Add it to your project:
> 
> ```
> $ uv add python-multipart
> ```
> This is because uploaded files are sent as "form data".
> 
> ## Import `File`[¶](#import-file)
> 
> Import `File` and `UploadFile` from `fastapi`:
> 
> ```
> from typing import Annotated
> from fastapi import FastAPI, File, UploadFile
> app = FastAPI()
> @app.post("/files/")
> async def create_file(file: Annotated[bytes, File()]):
> return {"file_size": len(file)}
> @app.post("/uploadfile/")
> async def create_upload_file(f

## 014 · cand-basic-014

- 原问题：What is covered in the documentation section 'Strict Content-Type Checking¶ (2a110100b77fb13ebb988a5ea9fac936bd69811f921eb5a285961d38274b7e14)'?
- 原预期答案：By default, FastAPI uses strict Content-Type header checking for JSON request bodies, this means that JSON requests must include a valid Content-Type header (e.g. application/json) in order for the body to be parsed as JSON.
- AI 预审：建议将章节概述改为具体知识问题，去掉文件哈希；答案支持范围需人工确认。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/2a110100b77fb13ebb988a5ea9fac936bd69811f921eb5a285961d38274b7e14.md)

来源摘录（最多 700 字符，可能截断）：

> # Strict Content-Type Checking[¶](#strict-content-type-checking)
> 
> By default, **FastAPI** uses strict `Content-Type` header checking for JSON request bodies, this means that JSON requests **must** include a valid `Content-Type` header (e.g. `application/json`) in order for the body to be parsed as JSON.
> 
> ## CSRF Risk[¶](#csrf-risk)
> 
> This default behavior provides protection against a class of **Cross-Site Request Forgery (CSRF)** attacks in a very specific scenario.
> 
> These attacks exploit the fact that browsers allow scripts to send requests without doing any CORS preflight check when they:
> 
> - don't have a `Content-Type` header (e.g. using`fetch()` with a`Blob` body)
> - and don't s

## 015 · cand-basic-015

- 原问题：What is covered in the documentation section 'Sub Applications - Mounts¶ (2ac0491c0a3279db9c4d733d116a23e1cfeea546f84011232fce81706035823b)'?
- 原预期答案：If you need to have two independent FastAPI applications, with their own independent OpenAPI and their own docs UIs, you can have a main app and "mount" one (or more) sub-application(s).
- AI 预审：建议将章节概述改为具体知识问题，去掉文件哈希；答案支持范围需人工确认。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/2ac0491c0a3279db9c4d733d116a23e1cfeea546f84011232fce81706035823b.md)

来源摘录（最多 700 字符，可能截断）：

> # Sub Applications - Mounts[¶](#sub-applications-mounts)
> 
> If you need to have two independent FastAPI applications, with their own independent OpenAPI and their own docs UIs, you can have a main app and "mount" one (or more) sub-application(s).
> 
> ## Mounting a **FastAPI** application[¶](#mounting-a-fastapi-application)
> 
> "Mounting" means adding a completely "independent" application in a specific path, that then takes care of handling everything under that path, with the *path operations* declared in that sub-application.
> 
> ### Top-level application[¶](#top-level-application)
> 
> First, create the main, top-level, **FastAPI** application, and its *path operations*:
> 
> ```
> from fastapi i

## 016 · cand-basic-016

- 原问题：What is covered in the documentation section 'Header Parameter Models¶ (2c0cc1fdf35af40f56ae922fd2f50f82ff77a7ee2bc5e22267a2bdf4a95c4397)'?
- 原预期答案：If you have a group of related header parameters, you can create a Pydantic model to declare them.
- AI 预审：建议将章节概述改为具体知识问题，去掉文件哈希；答案支持范围需人工确认。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/2c0cc1fdf35af40f56ae922fd2f50f82ff77a7ee2bc5e22267a2bdf4a95c4397.md)

来源摘录（最多 700 字符，可能截断）：

> # Header Parameter Models[¶](#header-parameter-models)
> 
> If you have a group of related **header parameters**, you can create a **Pydantic model** to declare them.
> 
> This would allow you to **re-use the model** in **multiple places** and also to declare validations and metadata for all the parameters at once. 😎
> 
> Note
> 
> This is supported since FastAPI version `0.115.0`. 🤓
> 
> ## Header Parameters with a Pydantic Model[¶](#header-parameters-with-a-pydantic-model)
> 
> Declare the **header parameters** that you need in a **Pydantic model**, and then declare the parameter as `Header`:
> 
> ```
> from typing import Annotated
> from fastapi import FastAPI, Header
> from pydantic import BaseModel
> a

## 017 · cand-basic-017

- 原问题：What is covered in the documentation section 'Path Operation Configuration¶ (3226cd853f7ef75f8767ead03717ac4315253df020f6707de764187014ae4a8d)'?
- 原预期答案：There are several parameters that you can pass to your path operation decorator to configure it.
- AI 预审：答案只说有若干参数，没有回答具体配置；需重写。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/3226cd853f7ef75f8767ead03717ac4315253df020f6707de764187014ae4a8d.md)

来源摘录（最多 700 字符，可能截断）：

> # Path Operation Configuration[¶](#path-operation-configuration)
> 
> There are several parameters that you can pass to your *path operation decorator* to configure it.
> 
> Warning
> 
> Notice that these parameters are passed directly to the *path operation decorator*, not to your *path operation function*.
> 
> ## Response Status Code[¶](#response-status-code)
> 
> You can define the (HTTP) `status_code` to be used in the response of your *path operation*.
> 
> You can pass directly the `int` code, like `404`.
> 
> But if you don't remember what each number code is for, you can use the shortcut constants in `status`:
> 
> ```
> from fastapi import FastAPI, status
> from pydantic import BaseModel
> app = Fast

## 018 · cand-basic-018

- 原问题：What is covered in the documentation section 'Learn¶ (3cde1bd348e9918da9f5d873be26b948b421795fce6233369aafeeb681eda074)'?
- 原预期答案：Here are the introductory sections and the tutorials to learn FastAPI.
- AI 预审：答案是目录引导，无明确技术知识点；建议替换。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/3cde1bd348e9918da9f5d873be26b948b421795fce6233369aafeeb681eda074.md)

来源摘录（最多 700 字符，可能截断）：

> # Learn[¶](#learn)
> 
> Here are the introductory sections and the tutorials to learn **FastAPI**.
> 
> You could consider this a **book**, a **course**, the **official** and recommended way to learn FastAPI. 😎

## 019 · cand-basic-019

- 原问题：What is covered in the documentation section 'Testing Events: lifespan and startup - shutdown¶ (45349e075c23e483bfc926ad9dcbd6f428973fbe83f1891a4daaf5414497a5dd)'?
- 原预期答案：When you need lifespan to run in your tests, you can use the TestClient with a with statement:
- AI 预审：建议将章节概述改为具体知识问题，去掉文件哈希；答案支持范围需人工确认。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/45349e075c23e483bfc926ad9dcbd6f428973fbe83f1891a4daaf5414497a5dd.md)

来源摘录（最多 700 字符，可能截断）：

> # Testing Events: lifespan and startup - shutdown[¶](#testing-events-lifespan-and-startup-shutdown)
> 
> When you need `lifespan` to run in your tests, you can use the `TestClient` with a `with` statement:
> 
> ```
> from contextlib import asynccontextmanager
> from fastapi import FastAPI
> from fastapi.testclient import TestClient
> items = {}
> @asynccontextmanager
> async def lifespan(app: FastAPI):
> items["foo"] = {"name": "Fighters"}
> items["bar"] = {"name": "Tenders"}
> yield
> # clean up items
> items.clear()
> app = FastAPI(lifespan=lifespan)
> @app.get("/items/{item_id}")
> async def read_items(item_id: str):
> return items[item_id]
> def test_read_items():
> # Before the lifespan starts, "items" is s

## 020 · cand-basic-020

- 原问题：What is covered in the documentation section 'Body - Multiple Parameters¶ (45b788bf9b2f7f5c21579fbb4405637643851f77e255b23930dc5e7e1434b3dd)'?
- 原预期答案：Now that we have seen how to use Path and Query, let's see more advanced uses of request body declarations.
- AI 预审：答案是章节过渡语，未解释多参数请求体；需重写。
- 人工决策：未填写。

[打开完整本地来源](../data/processed/web/fastapi_docs/45b788bf9b2f7f5c21579fbb4405637643851f77e255b23930dc5e7e1434b3dd.md)

来源摘录（最多 700 字符，可能截断）：

> # Body - Multiple Parameters[¶](#body-multiple-parameters)
> 
> Now that we have seen how to use `Path` and `Query`, let's see more advanced uses of request body declarations.
> 
> ## Mix `Path`, `Query` and body parameters[¶](#mix-path-query-and-body-parameters)
> 
> First, of course, you can mix `Path`, `Query` and request body parameter declarations freely and **FastAPI** will know what to do.
> 
> And you can also declare body parameters as optional, by setting the default to `None`:
> 
> ```
> from typing import Annotated
> from fastapi import FastAPI, Path
> from pydantic import BaseModel
> app = FastAPI()
> class Item(BaseModel):
> name: str
> description: str | None = None
> price: float
> tax: float |
