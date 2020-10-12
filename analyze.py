import streamlit as st
from pathlib import Path
from requests_html import HTML
import pandas as pd
import networkx as nx
from pyvis.network import Network
import pyvis.network as net
import base64
import shutil
from zipfile import ZipFile





def load_data(working_dir, restrict=True):
    
    def get_html_content_from_html(input_html):
        with open(input_html) as f:
            data = f.read()
            html = HTML(html=data)
        return html

    def extract_evernote_title_link_from_html(input_html):
        html = get_html_content_from_html(input_html)

        mydict = {}
        try:
            for item in html.find('a'):
                text = item.text
                link = list(item.links)[0]
                if link.startswith('evernote://'):
                    if not link in mydict:
                        mydict[link] = text
        except:
            pass

        return mydict
    
    def load_toc_tsv(tsv): # if use applescript out the note title link pair file
        toc_dict = {}
        df = pd.read_csv(tsv, sep='\t', header=None)
        df.columns = ['title', 'link']
        for item in df.iterrows():
            toc_dict[item[1][1]] = item[1][0]
        return toc_dict
    
    def load_toc_html(toc_html): # if generate Table of Contents manually
        toc_dict = extract_evernote_title_link_from_html(toc_html)
        return toc_dict
    
    def load_toc():
        toc_tsv_file = working_dir / "mydict.txt"
        toc_html_file = working_dir / "Table of Contents.html"

        if toc_tsv_file.exists(): # if use applescript out the note title link pair file
            toc_dict = load_toc_tsv(toc_tsv_file)
            return toc_dict
        elif toc_html_file.exists(): # if generate Table of Contents manually
            toc_dict = load_toc_html(toc_html_file)
            return toc_dict
        else:
            print("No TOC file found!")
            return None
        

    def generate_title_link_dict(link_title_dict):
        title_link_dict  = {}
        for k, v in link_title_dict.items():
            title_link_dict[v] = k
        return title_link_dict
    
        
        
    def build_databases(toc_dict, restrict=True):

        link_title_dict = toc_dict.copy()
        link_content_dict = {}
        connections = []
        
        for link, title in toc_dict.items():

            title = title.replace('?', '_')
            title = title.replace('/', '_')
            note_file = working_dir/f"{title}.html"
    
    
            link_content_dict[link] = get_html_content_from_html(note_file).text
            new_dict = extract_evernote_title_link_from_html(note_file)
            if new_dict:

                for k, v in new_dict.items():
                    if restrict: # only link note in box
                        if k in toc_dict:
                            connections.append([link, k])
                    
                    else:
                        connections.append([link, k])
                        if not k in link_title_dict:
                            link_title_dict[k] = v
                            
        return link_title_dict, link_content_dict, connections

                            
                            
                            

    try:
        toc_dict = load_toc()
        link_title_dict, link_content_dict, connections = build_databases(toc_dict, restrict=restrict)
        title_link_dict = generate_title_link_dict(link_title_dict)
        return link_title_dict, title_link_dict, link_content_dict, connections
    except:
        print("Error! Can not get Table of Contents")
        return None





# build the networkx graph
def build_nx_graph(connections, link_title_dict):
    graph = nx.DiGraph()
    for k, v in link_title_dict.items():
        graph.add_node(k)
    for [source, target] in connections:
        graph.add_edge(source, target)
    return graph





# build the pyvis graph
def build_pyvis_graph(nx_graph, link_title_dict, link_content_dict, node_shape_dict=None):
    graph = Network(notebook=True, directed=True)
    graph.from_nx(nx_graph)
    for node in graph.nodes:
        node['label'] = link_title_dict[node['id']]
        if node['id'] in link_content_dict:
            node['title'] = link_content_dict[node['id']]
        if node_shape_dict:
            node['value'] = node_shape_dict[node['id']]
    return graph





def fuzzy_query(query_term, title_link_dict):
    for k,v in title_link_dict.items():
        if k.find(query_term)>=0:
            return v





def build_and_display_pyvis_graph(nx_graph, link_title_dict, link_content_dict, node_shape_dict=None):
    pyvis_graph = build_pyvis_graph(nx_graph, link_title_dict, link_content_dict, node_shape_dict=node_shape_dict)
    pyvis_graph.show_buttons(filter_=['physics'])
    return pyvis_graph


def query_subgraph(nx_graph, query_term, title_link_dict):

    target_node = fuzzy_query(query_term, title_link_dict)
    sub_nx_graph = nx_graph.subgraph(nx.node_connected_component(nx_graph.to_undirected(), target_node))
    return sub_nx_graph


st.title("Visualization of Notes")

uploaded_file = st.sidebar.file_uploader("Choose zip file of exported notes folder", type="zip")



if uploaded_file is not None:

    restrict = not st.sidebar.checkbox("Show note outside the notebook")
    get_subgraph = st.sidebar.checkbox("Get subgraph")
    if get_subgraph:
        query_term = st.sidebar.text_input("Title to query")
    if st.sidebar.button('analyze now'):

        extract_path = 'extracted'
        if Path(extract_path).exists():
            shutil.rmtree(extract_path)
        with ZipFile(uploaded_file, 'r') as zipObj:
        # Extract all the contents of zip file in current directory
            zipObj.extractall(extract_path)
        working_dir = list(Path(extract_path).glob("*"))[0]

        st.write(working_dir.glob("*.html"))

        link_title_dict, title_link_dict, link_content_dict, connections = load_data(working_dir, restrict=restrict)
        nx_graph = build_nx_graph(connections, link_title_dict)
        pageranks = nx.pagerank(nx_graph)

        if get_subgraph and query_term:
            nx_graph = query_subgraph(nx_graph, query_term, title_link_dict)

        pyvis_graph = build_and_display_pyvis_graph(nx_graph, link_title_dict, link_content_dict, node_shape_dict=pageranks)
        output_html = "output.html"
        pyvis_graph.show(output_html)
        with open(output_html) as f:
            data = f.read()
        b64 = base64.b64encode(data.encode()).decode()  # some strings <-> bytes conversions necessary here
        href = f'<a href="data:text/html;base64,{b64}">Download HTML File</a> (right-click and choose \"save as\")'
        st.markdown(href, unsafe_allow_html=True)

