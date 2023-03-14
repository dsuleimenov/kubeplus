import sys
import json
import subprocess
import sys
import os
import yaml
import time

from logging.config import dictConfig

from flask import request
from flask import Flask, render_template

application = Flask(__name__)
app = application


dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    },
     'file.handler': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/root/kubeconfiggenerator.log',
            'maxBytes': 10000000,
            'backupCount': 5,
            'level': 'DEBUG',
        },
    },
    'root': {
        'level': 'INFO',
        'handlers': ['file.handler']
    }
})



def create_role_rolebinding(contents, name):
    filePath = os.getenv("HOME") + "/" + name
    fp = open(filePath, "w")
    #json_content = json.dumps(contents)
    #fp.write(json_content)
    yaml_content = yaml.dump(contents)
    fp.write(yaml_content)
    fp.close()
    print("---")
    print(yaml_content)
    print("---")
    cmd = " kubectl create -f " + filePath
    run_command(cmd)


def run_command(cmd):
    #print("Inside run_command")
    print(cmd)
    cmdOut = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()
    out = cmdOut[0].decode('utf-8')
    err = cmdOut[1].decode('utf-8')
    print(out)
    print("---")
    print(err)
    return out, err
    
    #if out != '':
    #    return out.decode('utf-8')
    #if err != '':
    #    return err.decode('utf-8')


class KubeconfigGenerator(object):

        def run_command(self, cmd):
                #print("Inside run_command")
                print(cmd)
                cmdOut = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()
                out = cmdOut[0].decode('utf-8')
                err = cmdOut[1].decode('utf-8')
                print(out)
                print("---")
                print(err)
                return out, err
                #if out != '':
                #        return out
                #        #printlines(out.decode('utf-8'))
                #print("Error:")
                #print(err)
                #if err != '':
                #        return err
                        #printlines(err.decode('utf-8'))

        def _create_kubecfg_file(self, sa, namespace, token, ca, server):
                top_level_dict = {}
                top_level_dict["apiVersion"] = "v1"
                top_level_dict["kind"] = "Config"

                contextName = sa

                usersList = []
                usertoken = {}
                usertoken["token"] = token
                userInfo = {}
                userInfo["name"] = sa
                userInfo["user"] = usertoken
                usersList.append(userInfo)
                top_level_dict["users"] = usersList

                clustersList = []
                cluster_details = {}
                cluster_details["server"] = server
                
                # TODO: Use the certificate authority to perform tls 
                # cluster_details["certificate-authority-data"] = ca
                cluster_details["insecure-skip-tls-verify"] = True

                clusterInfo = {}
                clusterInfo["cluster"] = cluster_details
                clusterInfo["name"] = sa
                clustersList.append(clusterInfo)
                top_level_dict["clusters"] = clustersList

                context_details = {}
                context_details["cluster"] = sa
                context_details["user"] = sa
                context_details["namespace"] = namespace
                contextInfo = {}
                contextInfo["context"] = context_details
                contextInfo["name"] = contextName
                contextList = []
                contextList.append(contextInfo)
                top_level_dict["contexts"] = contextList

                top_level_dict["current-context"] = contextName

                json_file = json.dumps(top_level_dict)
                fileName =  sa + ".json"

                fp = open(os.getenv("HOME") + "/" + fileName, "w")
                fp.write(json_file)
                fp.close()

                configmapName = sa + "-kubeconfig"
                created = False 
                while not created:        
                        cmd = "kubectl create configmap " + configmapName + " -n " + namespace + " --from-file=" + os.getenv("HOME") + "/" + fileName
                        self.run_command(cmd)
                        get_cmd = "kubectl get configmap " + configmapName + " -n "  + namespace
                        output, error = self.run_command(get_cmd)
                        if 'Error from server (NotFound)' in output:
                                time.sleep(2)
                                print("Trying again..")
                        else:
                                created = True


        def _apply_consumer_rbac(self, sa, namespace):
                role = {}
                role["apiVersion"] = "rbac.authorization.k8s.io/v1"
                role["kind"] = "ClusterRole"
                metadata = {}
                metadata["name"] = sa
                role["metadata"] = metadata

                # Read all resources
                ruleGroup1 = {}
                apiGroup1 = ["*",""]
                resourceGroup1 = ["*"]
                verbsGroup1 = ["get","watch","list"]
                ruleGroup1["apiGroups"] = apiGroup1
                ruleGroup1["resources"] = resourceGroup1
                ruleGroup1["verbs"] = verbsGroup1

                # Impersonate users, groups, serviceaccounts
                ruleGroup9 = {}
                apiGroup9 = [""]
                resourceGroup9 = ["users","groups","serviceaccounts"]
                verbsGroup9 = ["impersonate"]
                ruleGroup9["apiGroups"] = apiGroup9
                ruleGroup9["resources"] = resourceGroup9
                ruleGroup9["verbs"] = verbsGroup9

                # Pod/portforward to open consumerui
                ruleGroup10 = {}
                apiGroup10 = [""]
                resourceGroup10 = ["pods/portforward"]
                verbsGroup10 = ["create","get"]
                ruleGroup10["apiGroups"] = apiGroup10
                ruleGroup10["resources"] = resourceGroup10
                ruleGroup10["verbs"] = verbsGroup10

                ruleList = []
                ruleList.append(ruleGroup1)
                ruleList.append(ruleGroup9)
                ruleList.append(ruleGroup10)
                role["rules"] = ruleList

                roleName = sa + "-role-impersonate.yaml"
                create_role_rolebinding(role, roleName)

                roleBinding = {}
                roleBinding["apiVersion"] = "rbac.authorization.k8s.io/v1"
                roleBinding["kind"] = "ClusterRoleBinding"
                metadata = {}
                metadata["name"] = sa
                roleBinding["metadata"] = metadata

                subject = {}
                subject["kind"] = "ServiceAccount"
                subject["name"] = sa
                subject["apiGroup"] = ""
                subject["namespace"] = namespace
                subjectList = []
                subjectList.append(subject)
                roleBinding["subjects"] = subjectList

                roleRef = {}
                roleRef["kind"] = "ClusterRole"
                roleRef["name"] = sa
                roleRef["apiGroup"] = "rbac.authorization.k8s.io"
                roleBinding["roleRef"] = roleRef

                roleBindingName = sa + "-rolebinding-impersonate.yaml"
                create_role_rolebinding(roleBinding, roleBindingName)

        def _apply_provider_rbac(self, sa, namespace):
                role = {}
                role["apiVersion"] = "rbac.authorization.k8s.io/v1"
                role["kind"] = "ClusterRole"
                metadata = {}
                metadata["name"] = sa
                role["metadata"] = metadata

                # Read all resources
                ruleGroup1 = {}
                apiGroup1 = ["*",""]
                resourceGroup1 = ["*"]
                verbsGroup1 = ["get","watch","list"]
                ruleGroup1["apiGroups"] = apiGroup1
                ruleGroup1["resources"] = resourceGroup1
                ruleGroup1["verbs"] = verbsGroup1

                # CRUD on resourcecompositions et. al.
                ruleGroup2 = {}
                apiGroup2 = ["workflows.kubeplus"]
                resourceGroup2 = ["resourcecompositions","resourcemonitors","resourcepolicies","resourceevents"]
                verbsGroup2 = ["get","watch","list","create","delete","update","patch"]
                ruleGroup2["apiGroups"] = apiGroup2
                ruleGroup2["resources"] = resourceGroup2
                ruleGroup2["verbs"] = verbsGroup2

                # CRUD on clusterroles and clusterrolebindings
                ruleGroup3 = {}
                apiGroup3 = ["rbac.authorization.k8s.io"]
                resourceGroup3 = ["clusterroles","clusterrolebindings"]
                verbsGroup3 = ["get","watch","list","create","delete","update","patch"]
                ruleGroup3["apiGroups"] = apiGroup3
                ruleGroup3["resources"] = resourceGroup3
                ruleGroup3["verbs"] = verbsGroup3

                # CRUD on Port forward
                ruleGroup4 = {}
                apiGroup4 = [""]
                resourceGroup4 = ["pods/portforward"]
                verbsGroup4 = ["get","watch","list","create","delete","update","patch"]
                ruleGroup4["apiGroups"] = apiGroup4
                ruleGroup4["resources"] = resourceGroup4
                ruleGroup4["verbs"] = verbsGroup4

                # CRUD on platformapi.kubeplus
                ruleGroup5 = {}
                apiGroup5 = ["platformapi.kubeplus"]
                resourceGroup5 = ["*"]
                verbsGroup5 = ["get","watch","list","create","delete","update","patch"]
                ruleGroup5["apiGroups"] = apiGroup5
                ruleGroup5["resources"] = resourceGroup5
                ruleGroup5["verbs"] = verbsGroup5

                # CRUD on networkpolicies
                ruleGroup6 = {}
                apiGroup6 = ["networking.k8s.io"]
                resourceGroup6 = ["networkpolicies"]
                verbsGroup6 = ["get","watch","list","create","delete","update","patch"]
                ruleGroup6["apiGroups"] = apiGroup6
                ruleGroup6["resources"] = resourceGroup6
                ruleGroup6["verbs"] = verbsGroup6

                # CRUD on namespaces
                ruleGroup7 = {}
                apiGroup7 = [""]
                resourceGroup7 = ["namespaces"]
                verbsGroup7 = ["get","watch","list","create","delete","update","patch"]
                ruleGroup7["apiGroups"] = apiGroup7
                ruleGroup7["resources"] = resourceGroup7
                ruleGroup7["verbs"] = verbsGroup7

                # CRUD on HPA
                ruleGroup8 = {}
                apiGroup8 = ["autoscaling"]
                resourceGroup8 = ["horizontalpodautoscalers"]
                verbsGroup8 = ["get","watch","list","create","delete","update","patch"]
                ruleGroup8["apiGroups"] = apiGroup8
                ruleGroup8["resources"] = resourceGroup8
                ruleGroup8["verbs"] = verbsGroup8

                # Impersonate users, groups, serviceaccounts
                ruleGroup9 = {}
                apiGroup9 = [""]
                resourceGroup9 = ["users","groups","serviceaccounts"]
                verbsGroup9 = ["impersonate"]
                ruleGroup9["apiGroups"] = apiGroup9
                ruleGroup9["resources"] = resourceGroup9
                ruleGroup9["verbs"] = verbsGroup9

                # Exec into the Pods
                ruleGroup10 = {}
                apiGroup10 = [""]
                resourceGroup10 = ["pods/exec"]
                verbsGroup10 = ["get","create"]
                ruleGroup10["apiGroups"] = apiGroup10
                ruleGroup10["resources"] = resourceGroup10
                ruleGroup10["verbs"] = verbsGroup10

                ruleList = []
                ruleList.append(ruleGroup1)
                ruleList.append(ruleGroup2)
                ruleList.append(ruleGroup3)
                ruleList.append(ruleGroup4)
                ruleList.append(ruleGroup5)
                ruleList.append(ruleGroup6)
                ruleList.append(ruleGroup7)
                ruleList.append(ruleGroup8)
                ruleList.append(ruleGroup9)
                ruleList.append(ruleGroup10)
                role["rules"] = ruleList

                roleName = sa + "-role.yaml"
                create_role_rolebinding(role, roleName)

                roleBinding = {}
                roleBinding["apiVersion"] = "rbac.authorization.k8s.io/v1"
                roleBinding["kind"] = "ClusterRoleBinding"
                metadata = {}
                metadata["name"] = sa
                roleBinding["metadata"] = metadata

                subject = {}
                subject["kind"] = "ServiceAccount"
                subject["name"] = sa
                subject["apiGroup"] = ""
                subject["namespace"] = namespace
                subjectList = []
                subjectList.append(subject)
                roleBinding["subjects"] = subjectList

                roleRef = {}
                roleRef["kind"] = "ClusterRole"
                roleRef["name"] = sa
                roleRef["apiGroup"] = "rbac.authorization.k8s.io"
                roleBinding["roleRef"] = roleRef

                roleBindingName = sa + "-rolebinding.yaml"
                create_role_rolebinding(roleBinding, roleBindingName)

        def _apply_rbac(self, sa, namespace, entity=''):
                if entity == 'provider':
                        self._apply_provider_rbac(sa, namespace)
                if entity == 'consumer':
                        self._apply_consumer_rbac(sa, namespace)

        def _create_secret(self, sa, namespace):

                annotations = {}
                annotations['kubernetes.io/service-account.name'] = sa

                metadata = {}
                metadata['name'] = sa
                metadata['namespace'] = namespace
                metadata['annotations'] = annotations

                secret = {}
                secret['apiVersion'] = "v1"
                secret['kind'] = "Secret"
                secret['metadata'] = metadata
                secret['type'] = 'kubernetes.io/service-account-token'

                secretName = sa + "-secret.yaml"

                filePath = os.getenv("HOME") + "/" + secretName
                fp = open(filePath, "w")
                yaml_content = yaml.dump(secret)
                fp.write(yaml_content)
                fp.close()
                print("---")
                print(yaml_content)
                print("---")
                created = False
                while not created:
                    cmd = " kubectl create -f " + filePath
                    out, err = self.run_command(cmd)
                    if 'created' in out or 'AlreadyExists' in err:
                        created = True
                    else:
                        time.sleep(2)
                #print("Create secret:" + out)
                return out

        def _generate_kubeconfig(self, sa, namespace):
                cmdprefix = ""
                #cmd = " kubectl create sa " + sa + " -n " + namespace
                #cmdToRun = cmdprefix + " " + cmd
                #self.run_command(cmdToRun)

                #cmd = " kubectl get sa " + sa + " -n " + namespace + " -o json "
                #cmdToRun = cmdprefix + " " + cmd
                #out = subprocess.Popen(cmdToRun, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()[0]

                secretName = sa
                out = self._create_secret(secretName, namespace)
                print("Create secret:" + out)
                #if 'secret/' + sa + ' created' in out:
                if True: # do this always
                        #json_output = json.loads(out)
                        #secretName = json_output["secrets"][0]["name"]
                        #print("Secret Name:" + secretName)

                        tokenFound = False
                        while not tokenFound:
                                cmd1 = " kubectl describe secret " + secretName + " -n " + namespace
                                cmdToRun = cmdprefix + " " + cmd1
                                out1 = subprocess.Popen(cmdToRun, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()[0]
                                out1 = out1.decode('utf-8')
                                print(out1)
                                token = ''
                                for line in out1.split("\n"):
                                        if 'token' in line:
                                                parts = line.split(":")
                                                token = parts[1].strip()
                                if token != '':
                                        tokenFound = True
                                else:
                                        time.sleep(2)

                        print("Got secret token")
                        cmd1 = " kubectl get secret " + secretName + " -n " + namespace + " -o json "
                        cmdToRun = cmdprefix + " " + cmd1
                        out1 = subprocess.Popen(cmdToRun, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()[0]
                        out1 = out1.decode('utf-8')
                        json_output1 = json.loads(out1)
                        ca_cert = json_output1["data"]["ca.crt"].strip()
                        #print("CA Cert:" + ca_cert)

                        #cmd2 = " kubectl config view --minify -o json "
                        cmd2 = "kubectl -n default get endpoints kubernetes | awk '{print $2}' | grep -v ENDPOINTS"
                        cmdToRun = cmdprefix + " " + cmd2
                        out2 = subprocess.Popen(cmdToRun, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()[0]
                        #print("Config view Minify:")
                        print(out2)
                        out2 = out2.decode('utf-8')
                        #json_output2 = json.loads(out2)
                        #server = json_output2["clusters"][0]["cluster"]["server"].strip()
                        server = out2.strip()
                        server = "https://" + server
                        print("Kube API Server:" + server)
                        self._create_kubecfg_file(sa, namespace, token, ca_cert, server)

@app.route("/hello")
def index():
        return "hello world"



def flatten(yaml_contents, flattened, types_dict, prefix=''):
    for key in yaml_contents:
        value = yaml_contents[key]
        if isinstance(value, str):
            flattened[prefix + key] = value
            types_dict[key] = {'type': 'string'}
        if isinstance(value, bool):
            flattened[prefix + key] = value
            types_dict[key] = {'type': 'boolean'}
        elif isinstance(value, int):
            flattened[prefix + key] = value
            types_dict[key] = {'type': 'integer'}
        elif isinstance(value, float):
            flattened[prefix + key] = value
            types_dict[key] = {'type': 'float'}
        if isinstance(value, dict):
            inner_prop_dict = {}
            prop_dict = {'properties': inner_prop_dict}
            prop_dict['type'] = 'object'
            prop_dict['additionalProperties'] = True
            types_dict[key] = prop_dict
            if value:
                flatten(value, flattened, inner_prop_dict, prefix=prefix + key + ".")
                flattened[prefix + key] = value
            else:
                flattened[prefix + key] = {}
        if isinstance(value, list):
            types_dict[key] = {'type': 'array', 'items': {'type': 'string'}}
            if len(value) == 0:
                flattened[prefix + key] = []
            else:
                for l in value:
                    if isinstance(l, dict) or isinstance(l, list):
                        if isinstance(l, dict):
                            inner_prop_dict = {}
                            prop_dict = {'properties': inner_prop_dict}
                            prop_dict['type'] = 'object'
                            types_dict[key]['items'] = prop_dict
                            types_dict[key]['type'] = 'array'
                        if isinstance(l, list):
                            inner_prop_dict = {}
                            prop_dict = {'items': inner_prop_dict}
                            prop_dict['type'] = 'array'
                            types_dict[key]['items'] = prop_dict
                            types_dict[key]['type'] = 'array'
                        flatten(l, flattened, inner_prop_dict, prefix=prefix + key + ".")
                    else:
                        flattened[prefix + key] = l


def download_and_untar_chart(chartLoc, chartName):
    app.logger.info("download_and_untar_chart")

    if chartLoc.startswith("file"):
        parts = chartLoc.split("file:///")
        charttgz = parts[1].strip()
        chartLoc = "/" + charttgz
        app.logger.info("Chart Name:" + chartName)

    if chartLoc.startswith("https"):
        charttgz = chartName + ".tgz"
        wget = "wget -O /" + charttgz + " --no-check-certificate " + chartLoc
        app.logger.info("wget command:" + wget)
        out, err = run_command(wget)
        app.logger.info("wget output:" + out)
        app.logger.info("wget error:" + err)
        
    cmd = "tar -xvzf /" + charttgz
    out, err = run_command(cmd)

    app.logger.info("Output:" + out)
    app.logger.info("Error:" + err)


def get_chart_yaml(chartLoc, chartName):

    download_and_untar_chart(chartLoc, chartName)
    fp = open("/" + chartName + "/values.yaml", "r")
    data = fp.read()
    yaml_contents = yaml.safe_load(data)
    return yaml_contents


def check_and_install_crds(chartLoc, chartName=''):
    app.logger.info("Inside check_and_install_crds")
    download_and_untar_chart(chartLoc, chartName)
    crdLoc = '/' + chartName + '/crds'
    if os.path.exists(crdLoc):
        app.logger.info("CRDs exist in this chart. Installing them")
        cmd = 'kubectl create -f ' + crdLoc
        out, err = run_command(cmd)
        return True
    return False


def delete_chart_crds(chartName=''):
    app.logger.info("Inside delete_chart_crds")
    crdLoc = '/' + chartName + '/crds'
    if os.path.exists(crdLoc):
        app.logger.info("CRDs exist in this chart. Installing them")
        cmd = 'kubectl create -f ' + crdLoc
        out, err = run_command(cmd)


@app.route("/registercrd")
def registercrd():
    app.logger.info("Inside registercrd")
    kind = request.args.get("kind")
    version = request.args.get("version")
    group = request.args.get("group")
    plural = request.args.get("plural")
    chartURL = request.args.get("chartURL")
    chartName = request.args.get("chartName")

    app.logger.info("kind:" + kind)
    app.logger.info("version:" + version)
    app.logger.info("group:" + group)
    app.logger.info("plural:" + plural)
    app.logger.info("chartURL:" + chartURL)

    yaml_contents = get_chart_yaml(chartURL, chartName)
    app.logger.info("Values YAML:" + str(yaml_contents))

    flattened = {}
    attr_types = {}
    openAPIV3SchemaObj = {}
    openAPIV3SchemaProperties = {}
    openAPIV3SchemaPropertiesInner = {}
    openAPIV3SchemaPropertiesInnerDetails = {}
    openAPIV3SchemaPropertiesInner['type'] = 'object'
    openAPIV3SchemaPropertiesInner['properties'] = openAPIV3SchemaPropertiesInnerDetails
    openAPIV3SchemaProperties['spec'] = openAPIV3SchemaPropertiesInner
    openAPIV3SchemaProperties['status'] = {"type": "object", "properties": {"helmrelease": {"type": "string"}}}
    openAPIV3SchemaObj['type'] = 'object'
    openAPIV3SchemaObj['properties'] = openAPIV3SchemaProperties
    attr_types['openAPIV3Schema'] = openAPIV3SchemaObj
    flatten(yaml_contents, flattened, openAPIV3SchemaPropertiesInnerDetails)
    openAPIV3SchemaPropertiesInnerDetails["nodeName"] = {"type": "string"}

    json_contents = json.dumps(flattened)

    #print(json_contents)
    #print("===")
    attr_types_json = json.dumps(attr_types)
    #print(attr_types_json)

    crd = {}
    crd['apiVersion'] = "apiextensions.k8s.io/v1"
    crd['kind'] = "CustomResourceDefinition"
    crd['metadata'] = {'name':plural + "." + group}
    crd['spec'] = {"group":group, "names":{"kind": kind, "listKind": kind + "List","plural":plural,"singular":kind.lower()}, "scope": "Namespaced", "versions": [{"name": "v1alpha1", "schema": attr_types, "served": True, "storage": True}]}

#"status": {
#                                "properties": {
#                                    "helmrelease": {
#                                        "type": "string"
#                                    }
#                                },
#                                "type": "object"
#                            }


    crd_json = json.dumps(crd)
    app.logger.info("CRD JSON")
    app.logger.info(crd_json)

    crd_file_name = kind + ".json"
    fp = open("/" + crd_file_name, "w")
    fp.write(crd_json)
    fp.close()

    cmd = "kubectl create -f /" + crd_file_name
    out, err = run_command(cmd)
    app.logger.info("Output:" + out)
    app.logger.info("Error:" + err)

    check_and_install_crds(chartURL, chartName=chartName)

    return out

@app.route("/nodes")
def get_nodes():
    cmd = "kubectl get nodes "
    out, err = run_command(cmd)
    app.logger.info("Nodes: " + out)
    lines = out.split("\n")
    nodes = []
    for line in lines:
        app.logger.info(line)
        if 'NAME' not in line:
            parts = line.split(" ")
            nodeName = parts[0].strip()
            nodes.append(nodeName)

    nodesString = ",".join(nodes)
    app.logger.info("Node String:\n" + nodesString)
    return nodesString

@app.route("/testchart")
def testchart():
    chartURL = request.args.get('chartURL')
    if chartURL:
        print("Chart URL:" + chartURL)
        app.logger.info("Chart URL:" + chartURL)
    chartPath = request.args.get('chartPath')
    if chartPath:
        print("Chart Path:" + chartPath)
        app.logger.info("Chart Path:" + chartPath)

    chartLoc = ''
    if chartURL != None:
        chartLoc = chartURL
    elif chartPath != None:
        chartLoc = chartPath
    else:
        return "Error - chart Path is empty"

    #testChartName = "kubeplus-customerapi-reg-testchart"
    testChartName = "kptc"
    cmd = "helm install kptc " + chartLoc
    out, err = run_command(cmd)
    print(out)
    for line in out.split("\n"):
        if 'NAME' in line:
            parts = line.split(":")
            testChartName = parts[1].strip()
            break
    app.logger.info("Helm install output:" + out)
    print(err)
    app.logger.info("Helm install error:" + err)

    chartStatus = ''
    if err != '':
        chartStatus = err
    else:
        chartStatus = 'Chart is good.'

    cmd = "helm delete " + testChartName
    run_command(cmd)
    return chartStatus

def check_chart(chartURL, chartPath):
    if chartURL:
        print("Chart URL:" + chartURL)
        app.logger.info("Chart URL:" + chartURL)
    if chartPath:
        print("Chart Path:" + chartPath)
        app.logger.info("Chart Path:" + chartPath)

    chartLoc = ''
    if chartURL != None:
        chartLoc = chartURL
    elif chartPath != None:
        chartLoc = chartPath
    else:
        return "Error - chart Path is empty"

    origChartLoc = chartLoc
    message = ""
    if chartLoc.startswith("file"):
        parts = chartLoc.split("file:///")
        charttgz = parts[1].strip()
        chartLoc = "/" + charttgz

        if not os.path.exists(chartLoc):
            message = "Chart " + chartLoc + " not found.\n"
            message = message + "Use kubectl upload chart <charttgz> to upload the chart first."
            return message 
    return message


@app.route("/checkchartexists")
def checkchartexists():
    app.logger.info("Inside checkchartexists")
    chartURL = request.args.get('chartURL')
    chartPath = request.args.get('chartPath')
    message = check_chart(chartURL, chartPath)
    return message


@app.route("/dryrunchart")
def dryrunchart():
    chartURL = request.args.get('chartURL')
    chartPath = request.args.get('chartPath')
    message = check_chart(chartURL, chartPath)
    if message != "":
        return message

    #testChartName = "kubeplus-customerapi-reg-testchart"
    testChartName = "kptc"
    dryRunSuccess = False
    count = 0
    helmtemplate_op = ''

    chartStatus = ''

    #chart_crd_exist = check_and_install_crds(origChartLoc, chartName='kptc')
    #if chart_crd_exist and chartStatus != '':
    #    delete_chart_crds(chartName='kptc')
         
    chartLoc = ''
    if chartURL != None:
        chartLoc = chartURL
    elif chartPath != None:
        chartLoc = chartPath
    else:
        return "Error - chart Path is empty"

    if chartLoc.startswith("file"):
        parts = chartLoc.split("file:///")
        charttgz = parts[1].strip()
        chartLoc = "/" + charttgz

    chart_rbac_resources = []
    chart_perms = {}
    chart_perms_list = []
    while not dryRunSuccess and count < 1:
        cmd = "helm template kptc " + chartLoc 
        app.logger.info(cmd)
        out, err = run_command(cmd)

        print(out)
        #app.logger.info("Helm install output:" + out)
        print(err)
        #app.logger.info("Helm install error:" + err)

        if err.strip() == '':
            dryRunSuccess = True

            helmtemplate_op = out
            app.logger.info("Helm template OP:" + helmtemplate_op)
            yaml_contents = yaml.safe_load_all(helmtemplate_op)

            for doc in yaml_contents:
                if doc and (doc['kind'] == 'Role' or doc['kind'] == 'ClusterRole'):
                    rules = doc['rules']
                    app.logger.info(str(rules))
                    app.logger.info("------")
                    for r in rules:
                        app.logger.info(str(r))
                        apiGroups = []
                        if 'apiGroups' in r:
                            apiGroups = r['apiGroups']
                        resources = []
                        if 'resources' in r:
                            resources = r['resources']
                        resourceNames = []
                        if 'resourceNames' in r:
                            resourceNames = r['resourceNames']
                        nonResourceURLs = []
                        if 'nonResourceURLs' in r:
                            nonResourceURLs = r['nonResourceURLs']
                        verbs = []
                        if 'verbs' in r:
                            verbs = r['verbs']
                        res_action_list = []
                        for apiGroup in apiGroups:
                            if apiGroup in chart_perms:
                                res_action_list = chart_perms[apiGroup]
                            for res in resources:
                                res_action = {}

                                new_verbs = []
                                found_index = -1
                                for index, chart_res in enumerate(res_action_list):
                                    if res in chart_res:
                                        new_verbs = chart_res[res]
                                        found_index = index
                                        break

                                for v in verbs:
                                    if v not in new_verbs:
                                        new_verbs.append(v)
                                    if len(resourceNames) > 0:
                                        for resName in resourceNames:
                                            res_action[res + "/resourceName::" + resName] = new_verbs
                                    else:
                                        res_action[res] = new_verbs
                                if found_index >= 0:
                                    del res_action_list[found_index]
                                res_action_list.append(res_action)

                            chart_perms[apiGroup] = res_action_list
                        for nonResUrl in nonResourceURLs:
                            res_action = {}
                            res_action['nonResourceURL::' + nonResUrl] = verbs
                            res_action_list.append(res_action)
                            chart_perms['non-apigroup'] = [res_action]
        else:
            time.sleep(2)
            count = count + 1

    if err:
        return err

    chart_perms_dict = {}
    chart_perms_dict['chart_perms'] = chart_perms
    app.logger.info("Chart perms:" + json.dumps(str(chart_perms_dict)))

    # Check permissions
    cmd = "kubectl get configmap kubeplus-saas-provider-perms -o json -n " + namespace
    out1, err1 = run_command(cmd)
    app.logger.info("Perms Out:" + str(out1))
    app.logger.info("Perms Err:" + str(err1))
    kubeplus_perms = []
    if err1 == '' and out1 != '':
        json_op = json.loads(out1)
        perms = json_op['data']['kubeplus-saas-provider-perms.txt']
        app.logger.info(perms)
        k_perms = perms.split(",")
        for p in k_perms:
            p = p.replace("'","")
            p = p.replace("[","")
            p = p.replace("]","")
            p = p.strip()
            kubeplus_perms.append(p)

    # We don't want to compare signers as CRD like cert-manager have signers resource
    ignore_list = ['signers','certificatesigningrequests','localsubjectaccessreviews']

    missing_perms = {}
    for apiGroup, res_action_list in chart_perms.items():
        missing_res_action_list = []
        for res_perm in res_action_list:
            for res in res_perm.keys():
                if res not in kubeplus_perms or res in ignore_list:
                    missing_res_action_list.append(res_perm)
        if len(missing_res_action_list) > 0:
            missing_perms[apiGroup] = missing_res_action_list

    print("****")
    print(json.dumps(missing_perms))

    if missing_perms:
        missing_perms_json = {}
        missing_perms_json['perms'] = missing_perms
        missing_perms_json_obj = json.dumps(missing_perms_json)
        chartStatus = "KubePlus does not have the following permissions required by the Chart. Use provider-kubeconfig.py to add the missing permissions.\n"
        chartStatus = chartStatus + str(missing_perms_json_obj)

    # Check storage class used by pvc; the reclaim policy needs to be delete
    storage_classes = []
    pvc_count = 0
    storage_classname_count = 0

    kinds = []
    for line in out.split("\n"):
        line = line.strip()
        if line.startswith("kind:"):
            app.logger.info("Helm op:" + line)
            parts = line.split(":")
            kind = parts[1].strip()
            if kind != '' and kind != "":
                kinds.append(kind)
        if 'PersistentVolumeClaim' in line:
            pvc_count = pvc_count + 1
        if 'storageClassName' in line:
            storage_classname_count = storage_classname_count + 1
            parts = line.split(":")
            storage_class = parts[1].strip()
            app.logger.info("Storage class:" + storage_class)
            if storage_class not in storage_classes and storage_class != '' and storage_class != "":
                storage_classes.append(storage_class)
    if storage_classname_count < pvc_count: # this means there is a pvc with no storageClassName explicitly specified
        if 'standard' not in storage_classes:# it means the pvc defaults to the 'default' storageClassName; so add that.
            storage_classes.append('standard')
    app.logger.info("Storage classes:" + str(storage_classes))
    app.logger.info("Kinds:" + str(kinds))

    for storageClass in storage_classes:
        cmd = "kubectl get storageclass " + storageClass + " -o json "
        out, err = run_command(cmd)
        try:
            json_obj = json.loads(out)
            if 'reclaimPolicy' in json_obj:
                reclaim_policy = json_obj['reclaimPolicy']
                app.logger.info("Reclaim policy:" + reclaim_policy)
                if reclaim_policy.lower() != "delete":
                    chartStatus = "Storage class with reclaim policy " + reclaim_policy + " not allowed."
                    break
        except Exception as e:
            app.logger.info(str(e))

    # Check if chart contains Namespace object; Namespace object is not allowed in the chart.
    if 'Namespace' in kinds:
        chartStatus = chartStatus + ' Namespace object is not allowed in the chart.'

    if chartStatus == '':
        chartStatus = 'Chart is good.'

        # Append the list of kinds to chartStatus;
        # Also, include Namespace in the list of kinds to return.
        # We don't want Namespace in the chart but we do want it in the list of kinds
        # as KubePlus puts an annotation on all the kinds belonging to an app instance.
        kinds.append('Namespace')
        kindString = '-'.join(kinds)
        chartStatus = chartStatus + "\n" + kindString

    return chartStatus

def get_cpu_millis(cpu):
    app.logger.info("Inside get_cpu_millis. CPU:" + cpu)
    if cpu[len(cpu)-1] == 'm':
        int_cpu = int(cpu[:len(cpu)-1])
    else:
        int_cpu = int(cpu)
    app.logger.info("Integer milli cpu :" + str(int_cpu))
    return int_cpu

def get_memory_bytes(memory):
    app.logger.info("Inside get_memory_bytes. Memory:" + memory)
    int_mem = int(memory[:len(memory)-2])
    if 'Ki' in memory:
        int_mem = pow(2,10) *  int_mem
    if 'Mi' in memory:
        int_mem = pow(2,20) *  int_mem
    if 'Gi' in memory:
        int_mem = pow(2,30) *  int_mem
    if 'Ti' in memory:
        int_mem = pow(2,40) *  int_mem
    if 'Pi' in memory:
        int_mem = pow(2,50) *  int_mem
    if 'Ei' in memory:
        int_mem = pow(2,60) *  int_mem

    app.logger.info("Integer memory bytes:" + str(int_mem))
    return int_mem

@app.route("/cluster_capacity")
def get_cluster_capacity():
    cmd = 'kubectl get nodes -o json '
    out, err = run_command(cmd)

    node_info = []
    if out != '' and err == '':
        json_obj = json.loads(out)
        node_list = json_obj['items']
        total_allocatable_cpu = 0
        total_allocatable_memory = 0
        for node in node_list:
            node_data = {}
            node_data['name'] = node['metadata']['name']
            allocatable_cpu = node['status']['allocatable']['cpu']
            cpu_in_millis = get_cpu_millis(allocatable_cpu)
            node_data['allocatable_cpu'] = cpu_in_millis
            total_allocatable_cpu = total_allocatable_cpu + int(cpu_in_millis)

            allocatable_memory = node['status']['allocatable']['memory']
            memory_in_bytes = get_memory_bytes(allocatable_memory)
            node_data['allocatable_memory'] = memory_in_bytes
            total_allocatable_memory = total_allocatable_memory + memory_in_bytes
            node_info.append(node_data)

    cluster_info = {}
    cluster_info['nodes'] = node_info
    cluster_info['total_allocatable_cpu'] = total_allocatable_cpu * 1000
    total_allocatable_memory_gb = "{:.2f}".format(total_allocatable_memory / (1024 * 1024 * 1024))
    cluster_info['total_allocatable_memory'] = total_allocatable_memory
    cluster_info['total_allocatable_memory_gb'] = total_allocatable_memory_gb

    obj_to_ret = json.dumps(cluster_info)

    ret_string = "total_allocatable_cpu:" + str(cluster_info['total_allocatable_cpu']) + ",total_allocatable_memory_gb:" + str(cluster_info['total_allocatable_memory_gb'])

    app.logger.info("Cluster capacity:" + ret_string)

    return ret_string


@app.route("/network_policy")
def create_network_policy():
    app.logger.info("Inside create_network_policy")
    namespace = request.args.get('namespace')
    helmrelease = request.args.get('helmrelease')
    
    app.logger.info("Network Policy details:" + namespace + " " + helmrelease)

    netPol1 = {}
    netPol1["kind"] = "NetworkPolicy"
    netPol1["apiVersion"] = "networking.k8s.io/v1"
    netPol1MetaData = {}
    netPol1MetaData["name"] = "restrict-cross-ns-traffic"
    netPol1MetaData["namespace"] = namespace
    netPol1["metadata"] = netPol1MetaData
    netPol1Spec = {}
    netPol1PodSelector = {}
    netPol1PodSelector["matchLabels"] = {}
    netPol1Spec["podSelector"] = netPol1PodSelector

    netPol1IngressFromList = []
    netPol1IngressFrom = {}
    netPol1IngressPodSelector = {}
    netPol1IngressPodSelector["podSelector"] = {}
    netPol1IngressPodSelectorList = []
    netPol1IngressPodSelectorList.append(netPol1IngressPodSelector)
    netPol1IngressFrom["from"] = netPol1IngressPodSelectorList
    netPol1IngressFromList.append(netPol1IngressFrom)

    netPol1Spec["ingress"] = netPol1IngressFromList
    netPol1["spec"] = netPol1Spec

    app.logger.info("Network Policy:" + str(netPol1))

    json_file = json.dumps(netPol1)
    fileName =  "network-policy-deny-cross-traffic.json"

    fp = open(os.getenv("HOME") + "/" + fileName, "w")
    fp.write(json_file)
    fp.close()

    cmd = "kubectl create -f " + os.getenv("HOME") + "/" + fileName
    out, err = run_command(cmd)
    app.logger.info("Output of create network policy:")
    app.logger.info("Output:" + out)
    app.logger.info("Error:" + err)

    netPol2 = {}
    netPol2["kind"] = "NetworkPolicy"
    netPol2["apiVersion"] = "networking.k8s.io/v1"
    netPol2MetaData = {}
    netPol2MetaData["name"] = "allow-external-traffic"
    netPol2MetaData["namespace"] = namespace
    netPol2["metadata"] = netPol2MetaData
    netPol2Spec = {}
    netPol2PodSelector = {}
    netPol2MatchLabels = {}
    netPol2MatchLabels["partof"] = helmrelease
    netPol2PodSelector["matchLabels"] = netPol2MatchLabels
    netPol2Spec["podSelector"] = netPol2PodSelector

    netPol2Spec["ingress"] = [{}]
    netPol2["spec"] = netPol2Spec

    app.logger.info("Network Policy:" + str(netPol2))

    json_file = json.dumps(netPol2)
    fileName =  "allow-external-traffic.json"

    fp = open(os.getenv("HOME") + "/" + fileName, "w")
    fp.write(json_file)
    fp.close()

    cmd = "kubectl create -f " + os.getenv("HOME") + "/" + fileName
    out, err = run_command(cmd)

    err_string = str(err)
    return err_string


@app.route("/resource_quota")
def create_resource_quota():
    app.logger.info("Inside create_resource_quota..")
    namespace = request.args.get('namespace')
    helmrelease = request.args.get('helmrelease')
    cpu_req = request.args.get('cpu_req')
    cpu_lim = request.args.get('cpu_lim')
    mem_req = request.args.get('mem_req')
    mem_lim = request.args.get('mem_lim')

    app.logger.info("Quota details:" + namespace + " " + helmrelease + " " + cpu_req + " " + cpu_lim + " " + mem_req + " " + mem_lim)

    resQuota = {}
    resQuota["apiVersion"] = "v1"
    resQuota["kind"] = "ResourceQuota"
    resMetaData = {}
    resMetaData["name"] = helmrelease
    resMetaData["namespace"] = namespace
    resQuota["metadata"] = resMetaData
    quotaSpec = {}
    infraResSpec = {}
    infraResSpec["requests.cpu"] = cpu_req
    infraResSpec["requests.memory"] = mem_req
    infraResSpec["limits.cpu"] = cpu_lim
    infraResSpec["limits.memory"] = mem_lim
    quotaSpec["hard"] = infraResSpec
    resQuota["spec"] = quotaSpec

    app.logger.info("Resource Quota:" + str(resQuota))

    json_file = json.dumps(resQuota)
    fileName =  helmrelease + "-quota.json"

    fp = open(os.getenv("HOME") + "/" + fileName, "w")
    fp.write(json_file)
    fp.close()

    cmd = "kubectl create -f " + os.getenv("HOME") + "/" + fileName
    out, err = run_command(cmd)
    app.logger.info("Output of create quota:")
    app.logger.info("Output:" + out)
    app.logger.info("Error:" + err)

    err_string = str(err)
    return err_string


@app.route("/resourcecompositions")
def kp_state_restore():
    app.logger.info("Inside kp_state_restore...")
    cmd = "kubectl get resourcecompositions -A"
    out, err = run_command(cmd)
    app.logger.info(out)
    res_compositions = []
    if out != '':
        for line in out.split("\n"):
            line = line.strip()
            res_comp = {}
            if line and 'NAME' not in line:
                line1 = ' '.join(line.split())
                parts = line1.split(" ")
                ns = parts[0].strip()
                name = parts[1].strip()

                cmd1 = "kubectl get resourcecomposition " + name + " -n " + ns + " -o json"
                out1, err1 = run_command(cmd1)
                json_op = json.loads(out1)
                chartName = json_op['spec']['newResource']['chartName']
                chartURL = json_op['spec']['newResource']['chartURL']
                group = json_op['spec']['newResource']['resource']['group']
                kind = json_op['spec']['newResource']['resource']['kind']
                plural = json_op['spec']['newResource']['resource']['plural']
                version = json_op['spec']['newResource']['resource']['version']

                if 'respolicy' in json_op['spec']:
                    if 'policy' in json_op['spec']['respolicy']['spec']:
                        if 'podconfig' in json_op['spec']['respolicy']['spec']['policy']:
                            podconfig = json_op['spec']['respolicy']['spec']['policy']['podconfig']
                            res_comp['policy'] = json_op['spec']['respolicy']['spec']['policy']
                            if 'limits' in podconfig:
                                if 'cpu' in podconfig['limits']:
                                    res_comp['cpu_limits'] = podconfig['limits']['cpu']
                                if 'memory' in podconfig['limits']:
                                    res_comp['mem_limits'] = podconfig['limits']['memory']
                            if 'requests' in podconfig:
                                if 'cpu' in podconfig['requests']:
                                    res_comp['cpu_requests'] = podconfig['requests']['cpu']
                                if 'memory' in podconfig['requests']:
                                    res_comp['mem_requests'] = podconfig['requests']['memory']


                res_comp['name'] = name
                res_comp['namespace'] = ns
                res_comp['chartName'] = chartName
                res_comp['chartURL'] = chartURL
                res_comp['group'] = group
                res_comp['kind'] = kind
                res_comp['plural'] = plural
                res_comp['version'] = version
                res_compositions.append(res_comp)

                #output = "{} % {} % {} % {} % {} % {} % {} % {}".format(name, ns, chartName, chartURL, group, kind, plural, version)
    op = str(json.dumps(res_compositions))
    app.logger.info(op)
    return op 

@app.route("/update_provider_rbac")
def apply_rbac():
    namespace = request.args.get('kubeplusnamespace')
    resourceComposition = request.args.get('resourceComposition')
    targetNS = request.args.get('targetNS')

    cmd = '/root/kubectl get resourcecomposition ' + resourceComposition + " -n " + namespace + " -o json"
    out, _ = run_command(cmd)
    json_obj = json.loads(out)
    helm_chart = json_obj['spec']['newResource']['chartURL']
    print("Helm chart:" + helm_chart)
    app.logger.info("Helm chart:" + helm_chart)

    cmd = '/root/helm template kptc ' + helm_chart 
    out1, _ = run_command(cmd)
    kinds = []
    for line in out1.split("\n"):
        if 'kind' in line:
            parts = line.split(":")
            kind = parts[1].strip()
            if kind not in kinds:
                kinds.append(kind)
    print("Kinds in chart:" + str(kinds))
    app.logger.info("Kinds in chart:" + str(kinds))

    cmd = 'kubectl api-resources'
    out2, _ = run_command(cmd)
    kind_version_list = []
    for line in out2.split("\n"):
        line = line.strip()
        line1 = " ".join(line.split())
        if line1 != " ":
            parts = line1.split(" ")
            app.logger.info("Parts:" + str(parts))
            if parts[0] != '':
                found_kind = parts[len(parts)-1].strip()
                plural = parts[0].strip()
                kind_apiversion_map = {}
                app.logger.info("Found kind:" + found_kind)
                app.logger.info("Kinds:" + str(kinds))
                if found_kind in kinds:
                    app.logger.info("Inside if..")
                    kind_apiversion_map['kind'] = found_kind
                    apiversion = parts[2].strip()
                    if '/' not in apiversion:
                        apiversion = ""
                    kind_apiversion_map['apiversion'] = apiversion 
                    kind_apiversion_map['plural'] = plural
                    kind_version_list.append(kind_apiversion_map)

    app.logger.info("Kind APIVersion list:" + str(kind_version_list))

    role = {}
    role["apiVersion"] = "rbac.authorization.k8s.io/v1"
    role["kind"] = "Role"
    metadata = {}
    role_name = "kubeplus-saas-provider-update-role"
    metadata["name"] = role_name
    metadata["namespace"] = targetNS
    role["metadata"] = metadata

    ruleGroup9 = {}
    apiGroup9 = []
    resourceGroup9 = []
    verbsGroup9 = ["create", "delete", "update", "get"]

    for item in kind_version_list:
        if item['apiversion'] not in apiGroup9:
            apiGroup9.append(item['apiversion'])
        if item['plural'] not in resourceGroup9:
            resourceGroup9.append(item['plural'])

    apiGroup9.append("platformapi.kubeplus")
    resourceGroup9.append("'*'")
    ruleGroup9["apiGroups"] = apiGroup9 
    ruleGroup9["resources"] = resourceGroup9
    ruleGroup9["verbs"] = verbsGroup9
    app.logger.info("Rule Group:" + str(ruleGroup9))

    ruleList = []
    ruleList.append(ruleGroup9)
    role["rules"] = ruleList

    roleName = role_name + ".yaml" 
    create_role_rolebinding(role, roleName)

    role_binding_name = "kubeplus-saas-provider-update-rolebinding"
    roleBinding = {}
    roleBinding["apiVersion"] = "rbac.authorization.k8s.io/v1"
    roleBinding["kind"] = "RoleBinding"
    metadata = {}
    metadata["name"] = role_binding_name
    metadata["namespace"] = targetNS
    roleBinding["metadata"] = metadata

    subject1 = {}
    subject1["kind"] = "ServiceAccount"
    subject1["name"] = "kubeplus-saas-provider"
    subject1["apiGroup"] = ""
    subject1["namespace"] = namespace

    subject2 = {}
    subject2["kind"] = "ServiceAccount"
    subject2["name"] = "kubeplus-saas-consumer"
    subject2["apiGroup"] = ""
    subject2["namespace"] = namespace

    subjectList = []
    subjectList.append(subject1)
    subjectList.append(subject2)
    roleBinding["subjects"] = subjectList

    roleRef = {}
    roleRef["kind"] = "Role"
    roleRef["name"] = role_name
    roleRef["apiGroup"] = "rbac.authorization.k8s.io"
    roleBinding["roleRef"] = roleRef

    roleBindingName = role_binding_name + ".yaml"
    create_role_rolebinding(roleBinding, roleBindingName)
    
    return "abc"

if __name__ == '__main__':
        kubeconfigGenerator = KubeconfigGenerator()
        namespace = sys.argv[1]

        # Note that the reason we are not applying RBAC to consumer and provider
        # kubeconfigs here is because the RBAC policies are applied when the SA
        # is created (in the Helm chart)

        # 2. Generate/Retrieve Consumer kubeconfig
        sa = 'kubeplus-saas-consumer'
        kubeconfigGenerator._generate_kubeconfig(sa, namespace)
        #kubeconfigGenerator._apply_rbac(sa, namespace, entity='consumer')
        
        # We are commenting out retrieval of Provider kubeconfig here as we have
        # now extracted out Provider kubeconfig generation in a step that will 
        # have to be run first.
        # 1. Generate Provider kubeconfig
        #sa = 'kubeplus-saas-provider'
        #kubeconfigGenerator._generate_kubeconfig(sa, namespace)
        #kubeconfigGenerator._apply_rbac(sa, namespace, entity='provider')
        
        app.run(host='0.0.0.0', port=5005)

