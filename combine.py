import re
from os import listdir

from PyPDF2 import PdfFileMerger
from PyPDF2 import PdfFileReader

# 临时存放单个页面pdf的目录
gitbook_tmppdf_dir = './'
# 生成的目标pdf文件
output_pdf = "gitbook.pdf"

pdfs_hierarchy = {}

def load_pdf_hierarchy_imp(path,prefix,pdfs,parent):
    re_str = "\[%s_(\d+)\].+\.pdf"%(prefix)
    p = re.compile(re_str)
    for f in listdir(path):
        v = p.findall(f)
        if v:
            id = int(v[0])
            this_prefix = "%s_%s"%(prefix,v[0])
            children = {}
            raw = f[len("[%s]"%(this_prefix)):]
            raw = raw[:-4]
            this = {
                "id": id,
                "name": "%s/%s"%(path,f),
                "raw": raw,
                "children": children,
                "parent": parent
            }
            pdfs[id] = this
            load_pdf_hierarchy_imp(path,this_prefix,children,this)

def load_pdf_hierarchy(path,pdfs):
    load_pdf_hierarchy_imp(path, "", pdfs, None)

def print_pdf_hierarchy(pdfs):
    for k in sorted(pdfs):
        p = pdfs[k]["parent"]
        p = p["id"] if p else 0
        print("%s %s | %s | %s" % (k, p, pdfs[k]["name"], pdfs[k]["raw"]))
        print_pdf_hierarchy(pdfs[k]["children"])


def combine_imp(merger,pdfs,cur_page, parent):
    for k in sorted(pdfs):
        v = pdfs[k]
        page_filename = v["name"]
        page = PdfFileReader(page_filename)
        page_cnt = page.getNumPages()
        page_filename = v["raw"]

        merger.append(page)
        p = merger.addBookmark(page_filename, cur_page, parent)
        cur_page += page_cnt
        cur_page = combine_imp(merger,v["children"],cur_page, p)

    return cur_page

def combine(pdfs,output):
    merger = PdfFileMerger()
    combine_imp(merger,pdfs,0,None)
    merger.write(output)

if __name__ == '__main__':
    load_pdf_hierarchy(gitbook_tmppdf_dir,pdfs_hierarchy)
    print_pdf_hierarchy(pdfs_hierarchy)
    combine(pdfs_hierarchy,output_pdf)