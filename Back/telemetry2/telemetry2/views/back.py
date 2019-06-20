import datetime
from vincenty import vincenty
import os
import uuid
import shutil
import logging
import random
from copy import deepcopy
import sys
import json
import pandas as pd 
import numpy as np
from math import radians, sin, cos, acos
from pyramid.view import view_config
from pyramid.response import Response
from pyramid.request import Request

#Algorithm from csv file
@view_config(route_name='upload', renderer='json',request_method='POST')
def init_upload(request):
    objFile = request.POST.get('file') # gets csv file uploaded from Front app
    WantedData=['event-id','timestamp','location-lat','location-long'] # à demander en paramètres d'entrée
    rawPointsDf = DataFrameManagement(objFile,WantedData) # function to have a df with expected data
    trustedPointsdf,eleminatedPointsdf=prefilterData(rawPointsDf)
    candidateDf = rawPointsDf.loc[(~rawPointsDf['id'].isin(eleminatedPointsdf.id))]
    duplicatesToDelete = findDuplicates(candidateDf)
    workingDf = pd.concat([candidateDf, duplicatesToDelete]).drop_duplicates(keep=False)
    workingDf.insert(len(workingDf.columns),'status','pending')
    points_prefiltered = dfToListDict(workingDf)
    points_filtered1=Distance_algo(points_prefiltered,100,100) # seuils à modifier
    points_filtered2=Speed_algo(points_filtered1,100,130) # seuils à modifier

    return dfToListDict(rawPointsDf),points_prefiltered,dfToListDict(eleminatedPointsdf),points_filtered2

def DataFrameManagement(objFile,WantedData):
    data = pd.read_csv(objFile.file,dtype=str)
    dataM=data[WantedData] # Keep only WantedData from the dataframe
    L=len(dataM.columns)
    ExpectedLabels = ['id','date','LAT','LON','elevation','HDOP','info'] # list of labels of the most complete dataset 
    dataM.columns = ExpectedLabels[:L]
    for i in ExpectedLabels[L:]:
        dataM.insert(len(dataM.columns),i,'')
    dataM['date'] = dataM['date'].str.replace(" ","T") #to have date in appropiate format
    dataM['date'] = pd.to_datetime(dataM["date"]).dt.strftime('%Y-%m-%dT%H:%m:%s')
    dataM = dataM.sort_values(by='date',ascending=True)
    dataM = dataM.replace({'':np.NAN})

    return dataM

#Aglorithm from data in textarea
@view_config(route_name='backapp', renderer='json',request_method='POST')
def init_back(request):
    #log.debug('%s %s', request, request.params)
    if "geometry" in request.POST:
        geometry = request.POST.get('geometry')
        pb=[]
        #step1 parsing data
        points_distinct,pb=parsingRequest(geometry,pb)
        # ordered by date
        rawPointsDf=orderByDate(points_distinct)
        #step2 prefiltre
        trustedPointsdf,eleminatedPointsdf=prefilterData(rawPointsDf)
        #step3 estimation
        if len(pb)==0:
            candidateDf = rawPointsDf.loc[(~rawPointsDf['id'].isin(eleminatedPointsdf.id))]
            

            # to delete duplicates
            duplicatesToDelete = findDuplicates(candidateDf)
            
            workingDf = pd.concat([candidateDf, duplicatesToDelete]).drop_duplicates(keep=False)

            # points_prefiltered=annotatedResult(rawPointsDf,eleminatedPointsdf,trustedPointsdf,workingDf)

            # to delete points very far from other data
            workingDf.insert(len(workingDf.columns),'status','pending')
            points_prefiltered = dfToListDict(workingDf)

            # points_prefiltered = workingDf.to_dict('Index').values()
            points_filtered1=Distance_algo(points_prefiltered,2,10)
            # Add speed info 
            points_filtered2=Speed_algo(points_filtered1,2,50)
            return points_distinct,points_prefiltered,dfToListDict(eleminatedPointsdf),points_filtered2 # ,duplicates
        else :
            return 'souci'
    else:
        return 'no params'

def dfToListDict(dataframe):
    toret = []
    dataframe = dataframe.replace({np.NAN:None})
    rows = dataframe.to_dict('Index').values()
    for row in rows:
        toret.append(row)
    return  toret


def parsingRequest(options,pb):
    points=options.split('\n')
    points_distinct=[]    
    i=0
    long=len(points)
    while i < long : 
        tempData = points[i].split(',')
        nbCol = len(tempData)
        if nbCol < 3:
            pb.append(1)
        else:
            points_distinct.append({
                'id':tempData[0] if 0 < nbCol else '' ,
                'date':tempData[1] if 1 < nbCol else '',
                'LAT':tempData[2] if 2 < nbCol else '' , 
                'LON':tempData[3] if 3 < nbCol else '' ,
                'elevation': tempData[4] if 4 < nbCol else '',
                'HDOP': tempData[5] if 5 < nbCol else '' ,
                'info': tempData[6] if 6 < nbCol else ''
            })
        i=i+1
    return points_distinct, pb
   
def orderByDate(data):
    pFrame = pd.DataFrame(data)
    pFrame['date'] = pd.to_datetime(pFrame["date"]).dt.strftime('%Y-%m-%dT%H:%m:%s')
    pFrame = pFrame.sort_values(by='date',ascending=True)
    pFrame = pFrame.replace({'':np.NAN})
    return pFrame 


def prefilterData(data):
    eleminatedPointsdf = findPointsToEliminate(data)
    trustedPointsdf = findTrustedPoints(data)
    return trustedPointsdf , eleminatedPointsdf

def findPointsToEliminate(data):
    return data.loc[~data['info'].isin(['2D','3D',np.NAN])]
    
def findTrustedPoints(data):
    return data.loc[(data['HDOP']=='0.7') & (data['info'].isin(['2D','3D',np.NAN]))]

def algoConfigParameters():
    parametersToEnter = {
        'MAXSPEEDRATE':'',
        'MAXALT':'',
        'MINALT':'',
     }
    return 0

def annotatedResult(rawPointsDf,eleminatedPointsdf,trustedPointsdf):
    pendingPointsDf=rawPointsDf.loc[(~rawPointsDf['id'].isin(eleminatedPointsdf.id))&(~rawPointsDf['id'].isin(trustedPointsdf.id))]
    pendingPointsDf.insert(len(pendingPointsDf.columns),'status','pending')
    
    return dfToListDict(pendingPointsDf)
    # points_prefiltered = []
    
    # rows = pendingPointsDf.to_dict('Index').values()
    # for row in rows:
    #     points_prefiltered.append(row)
    # return  points_prefiltered

# def annotatedResult(df,trustedPointsList,eleminatedPointsList):
#     points_prefiltered=[]
#     m = df.to_dict('Index').values()
#     for item in m:
#         item['status']='pending'
#         points_prefiltered.append(item)
#     for itemt in trustedPointsList:
#         points_prefiltered[itemt]['status'] = 'trust'
#     for iteme in eleminatedPointsList:
#         points_prefiltered[iteme]['status'] = 'toEliminate'

#     return  points_prefiltered

def findDuplicates(candidateDf):
    allDuplicatedDf = candidateDf[candidateDf.duplicated(['date'],keep=False)]
    listDateGroup = allDuplicatedDf['date'].unique().tolist()
    duplicatedRowsToDelete = None

    for date in listDateGroup:
        currentDf = allDuplicatedDf.loc[allDuplicatedDf['date']==date]
        currentDf.insert(len(allDuplicatedDf.columns),'total',0)
        currentDf['total'] = currentDf.isnull().sum(axis=1)
        currentDfOrdered = currentDf.sort_values(by='total',ascending=True)
        duplicatedRowsToDelete = pd.concat([currentDfOrdered[1:],duplicatedRowsToDelete])
        if duplicatedRowsToDelete is not None:
            duplicatedRowsToDelete = duplicatedRowsToDelete.drop(['total'] , axis=1)
    return duplicatedRowsToDelete


    Nduplicates = []
    L=len(data)
    for i in range(L-1):
        if data[i]['date']==data[i+1]['date']:
            S1=sum(value == '' for value in data[i].values())
            S2=sum(value == '' for value in data[i+1].values())
            if S1<S2:
                Nduplicates.append(data[i])
            elif S1>S2:
                Nduplicates.append(data[i+1])
            else :
                Nduplicates.append(data[i])
        else: 
            Nduplicates.append(data[i])
    if data[L-2]['date']!=data[L-1]['date']:
        Nduplicates.append(data[L-1])
    return Nduplicates

# Version qui laisse les points trop éloignés en pending
# def Distance_algo(points):
#     pointsfiltered=deepcopy(points)
#     L=len(pointsfiltered)
#     #MAX=100
#     pointsfiltered[0]['distance1'] = 0
#     for i in range (L-1):
#         slat = radians(float(pointsfiltered[i]['LAT']))
#         slon = radians(float(pointsfiltered[i]['LON']))
#         elat = radians(float(pointsfiltered[i+1]['LAT']))
#         elon = radians(float(pointsfiltered[i+1]['LON']))
#         dist = 6371.01 * acos(sin(slat)*sin(elat) + cos(slat)*cos(elat)*cos(slon - elon))
#         pointsfiltered[i+1]['distance1'] = dist
#         if pointsfiltered[i+1]['distance1']< 2:
#             pointsfiltered[i]['status']='retained'
#             pointsfiltered[i+1]['status']='retained'
#         if i<=1:
#             pointsfiltered[i]['distance2'] = 0
#         else:
#             tlat = radians(float(pointsfiltered[i-2]['LAT']))
#             tlon = radians(float(pointsfiltered[i-2]['LON']))
#             dist2 = 6371.01 * acos(sin(slat)*sin(tlat) + cos(slat)*cos(tlat)*cos(slon - tlon))
#             pointsfiltered[i]['distance2']=dist2
#             if pointsfiltered[i]['distance2'] < 2:
#                 pointsfiltered[i]['status']='retained'
#     slat = radians(float(pointsfiltered[L-1]['LAT']))
#     slon = radians(float(pointsfiltered[L-1]['LON']))
#     tlat = radians(float(pointsfiltered[L-3]['LAT']))
#     tlon = radians(float(pointsfiltered[L-3]['LON']))
#     dist2 = 6371.01 * acos(sin(slat)*sin(tlat) + cos(slat)*cos(tlat)*cos(slon - tlon))
#     pointsfiltered[L-1]['distance2']=dist2 
#     return pointsfiltered

#Version delete far points + calculated distance with Vicenty
def Distance_algo(points,max1,max2):
    pointsfiltered=[]
    L=len(points)
    #MAX=100
    points[0]['distance1'] = 0
    for i in range (L-1):
        points[i+1]['distance1'] = vincenty((float(points[i]['LAT']),float(points[i]['LON'])),(float(points[i+1]['LAT']),float(points[i+1]['LON'])))
        if points[i+1]['distance1']< max1:
            points[i]['status']='retained'
            points[i+1]['status']='retained'
        if i<=1:
            points[i]['distance2'] = 0
        else:
            points[i]['distance2']=vincenty((float(points[i-2]['LAT']),float(points[i-2]['LON'])),(float(points[i]['LAT']),float(points[i]['LON'])))
            if points[i]['distance2'] < max2:
                points[i]['status']='retained'
        if points[i]['status']=='retained':
            pointsfiltered.append(points[i])
    points[L-1]['distance2']=vincenty((float(points[L-3]['LAT']),float(points[L-3]['LON'])),(float(points[L-1]['LAT']),float(points[L-1]['LON'])))
    if points[L-1]['distance2'] <max2:
        points[L-1]['status']='retained'
    if points[L-1]['status']=='retained':
        pointsfiltered.append(points[L-1])
    return pointsfiltered

def Speed_algo(points,max1,MaxSpeed):
    pointsfilteredS=[]
    speed=0
    L=len(points)
    points[0]['speed']=0
    pointsfilteredS.append(points[0])
    for i in range(1,L):
        diftimeS=datetime.datetime.strptime(points[i]['date'],'%Y-%m-%d %H:%M:%S') - datetime.datetime.strptime(points[i-1]['date'],'%Y-%m-%d %H:%M:%S')
        diftimeH=diftimeS.total_seconds()/3600
        if 0<points[i]['distance1']<max1: #à voir pour la distance
            speed=points[i]['distance1']/float(diftimeH)
        else:
            speed=points[i]['distance2']/float(diftimeH)
        points[i]['speed']=speed
        if points[i]['speed']<MaxSpeed: #à voir pour la valeur en fonction de l'espèce (50 voire 70 en pointe pour bouquetin)
            pointsfilteredS.append(points[i])
    return pointsfilteredS
        


    

