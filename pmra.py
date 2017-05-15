import json
import datetime
import os.path
import requests
from bs4 import BeautifulSoup
import time
import sys
from evaluator import Evaluator
from metrics import Metrics
from filewriter import FileWriter

test_set_path = "testSet"
training_set_path = "trainingSet"
topics = 200
passes = 1
test_set_limit = 200
threshold_start = 1
threshold_end = 10
base_search_url = "https://www.ncbi.nlm.nih.gov/pubmed?linkname=pubmed_pubmed&from_uid="
base_doc_url = "https://www.ncbi.nlm.nih.gov/pubmed/"
thresholds = []
metrics_obj_list = []

def getTime():
    return str(datetime.datetime.time(datetime.datetime.now()))

def tlog(msg):
    print("["+getTime()+"] "+msg)

def printProgressBar(progress, total):
    prog_bar = ""
    padding = ""
	#int(100*ratio) so we get something like e.g. int(0.733435*100) = 73, halved, to print 50 '=' maximum
    prog = int(int(100*progress / total)*0.5)
    for i in range(prog):
        prog_bar += "="
    for i in range(50-prog):
        padding += " "
    if(int(progress/total) < 1):
        percentage = int(100*progress/total)
        print("\t["+prog_bar+padding+"] " + str(percentage)+"%", end="\r")
        sys.stdout.flush()
    else:
        print("\t["+prog_bar+padding+"] 100%")
        print()

def getResults(test_set_ids):
    if os.path.exists("results.json"):
        results_file = open("results.json","r")
        pmid_results = json.load(results_file)
    else:
        pmid_results = {}

        i = 0
        for doc_id in test_set_ids:
            search_url = base_search_url + str(doc_id)
            search_page = requests.get(search_url)

            html = BeautifulSoup(search_page.text)
            results = html.body.find_all("div", attrs={"class":"rprt"})[0:11]

            pmid_results[doc_id] = []

            for result in results:
                title_p = result.find("p", attrs={"class":"title"})
                pmid = title_p.find("a").get("href").split("/")[-1]
                if pmid != doc_id:
                    pmid_results[doc_id].append(pmid)

            i+=1
            printProgressBar(i, len(test_set_ids))

            time.sleep(3)

        results_file = open("results.json", "w")
        results_file.write(json.dumps(pmid_results))

        tlog("Saved results to results.json.")

    return pmid_results

start_time = getTime()

if test_set_limit !=-1:
    test_set = json.load(open(test_set_path))["documents"][0:test_set_limit]
else:
    test_set = json.load(open(test_set_path))["documents"]

test_set_pmids = [doc["pmid"] for doc in test_set]
tlog("Test set read.")


fw = FileWriter()

for i in range(threshold_start, threshold_end+1):
    thresholds.append(i)
    metrics_obj_list.append(Metrics())

eval = Evaluator()

pmid_results = getResults(test_set_pmids)

results_map = {}
i=0
end = len(test_set)*10
for doc in test_set:
    doc_id = doc["pmid"]
    results = pmid_results[doc_id]

    result_docs = []

    for result_id in results:
        result_doc = {}
        result_doc["pmid"] = result_id

        #Get mesh major and add it do result_doc map
        doc_page = base_doc_url+result_id
        print(doc_page)

        requested_page = requests.get(doc_page)
        html = BeautifulSoup(requested_page.text)

        mesh_html = html.find("div",attrs={"class":["ui-ncbi-toggler-slave", "ui-ncbitoggler", "ui-ncbitoggler-slave-open"]}).find_all("ul")

        for ul_list in mesh_html:
            if ul_list.findPrevious().text == "MeSH terms":
                mesh_ul_list = ul_list
                break

        mesh_terms = [x.find("a").text.split("/")[0] for x in mesh_ul_list]

        result_doc["meshMajor"] = mesh_terms

        result_docs.append(result_doc)

        i+=1
        printProgressBar(i, end)

        time.sleep(3)

    results_map[doc_id] = result_docs

    for k in range(0, len(thresholds)):
        threshold = thresholds[k]

        eval.query(result_docs[0:threshold], doc)
        eval.calculate()

        metrics_obj_list[k].updateMacroAverages(eval)

results_map_file = open("results_map.json", "w")
results_map_file.write(json.dumps(results_map))

for obj in metrics_obj_list:
    obj.calculate(len(test_set))

tlog("Done getting results. Writing to files.")
fw.writeToFiles(metrics_obj_list, thresholds)

tlog("Done.")
