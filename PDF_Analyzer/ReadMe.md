## PDF Parsing Pipeline

install dependencies
```
pip install -r requirements.txt
```

## 0-pdf2json.py
converts pdf documents to JSON objects. The first page of each document is converted to markdown, and inserted into the system prompt as context.

```
python 0-pdf2json.py
```
copy path to pdf file, and path to output directory

Will outputs pairs of .jpeg and .json files, which can be viewed together to verify json output. 

Output should be manually verified, as occasionally only a portion of the page is rendered. 

## 1-reanalyze-jpeg.py
In case of an error, reanalyze the jpeg file.

```
python 1-reanalyze-jpeg.py
```

