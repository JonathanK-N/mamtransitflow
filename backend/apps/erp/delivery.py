"""Preuves de livraison signées. Auteur : Jonathan Kakesa (JonathanK-N)."""
import hashlib
import io
import json
import math
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from . import models as m, services
from .views import ScopedView
from .views import Page

CONSENT = 'Je confirme la réception selon les quantités et réserves indiquées et accepte de signer ce justificatif.'


class DeliveryDocumentsView(ScopedView):
    def get(self,request,pk):
        self.ensure('documents')
        trip=get_object_or_404(self.queryset('missions'),pk=pk)
        documents=m.Document.objects.filter(organization=self.org,mission=trip,category='delivery')
        paginator=Page();page=paginator.paginate_queryset(documents,request)
        return paginator.get_paginated_response([{'id':str(x.pk),'title':x.title,'shared_with_customer':x.shared_with_customer} for x in page])
    def post(self,request,pk):
        if not self.enabled('documents'):raise PermissionDenied('L’application Documents est désactivée.')
        if self.member.role not in ('owner','admin','operations','driver'):raise PermissionDenied()
        m.Organization.objects.select_for_update().get(pk=self.org.pk)
        trip=get_object_or_404(self.queryset('missions'),pk=pk)
        if trip.status not in ('active','completed'):raise ValidationError('Démarrez la mission avant de joindre ses justificatifs.')
        from .serializers import serializer_for
        serializer=serializer_for(m.Document)(data={'title':request.data.get('title'),'file':request.data.get('file'),
            'shared_with_customer':request.data.get('shared_with_customer',False),'category':'delivery','mission':str(trip.pk),'vehicle':str(trip.vehicle_id)},context=self.context())
        serializer.is_valid(raise_exception=True)
        document=serializer.save(organization=self.org)
        services.audit(self.org,request.user,'delivery-document',document,mission=str(trip.pk))
        return Response({'id':str(document.pk),'title':document.title,'shared_with_customer':document.shared_with_customer},status=201)


def strokes(value):
    if not isinstance(value,list) or not 1<=len(value)<=100:
        raise ValidationError('Tracez la signature du destinataire.')
    normalized=[];total=0;length=0
    for stroke in value:
        if not isinstance(stroke,list) or not 2<=len(stroke)<=2000:
            raise ValidationError('Tracé de signature invalide.')
        total+=len(stroke)
        if total>4000:raise ValidationError('Signature trop détaillée. Effacez puis signez à nouveau.')
        points=[]
        for point in stroke:
            if not isinstance(point,list) or len(point)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in point):
                raise ValidationError('Point de signature invalide.')
            x,y=point
            if not 0<=x<=600 or not 0<=y<=200:raise ValidationError('Signature hors du cadre.')
            points.append([round(x,2),round(y,2)])
        length+=sum(math.dist(a,b) for a,b in zip(points,points[1:]))
        normalized.append(points)
    if length<20:raise ValidationError('La signature est vide ou trop courte.')
    return normalized


def receipt_data(receipt):
    return dict(id=str(receipt.pk),recipient_name=receipt.recipient_name,reservations=receipt.reservations,
        signature=receipt.signature,snapshot=receipt.snapshot,digest=receipt.digest,signed_at=receipt.signed_at)


class ReceiptView(ScopedView):
    def get(self,request,pk,pdf=False):
        trip=get_object_or_404(self.queryset('missions'),pk=pk)
        receipt=m.DeliveryReceipt.objects.filter(organization=self.org,mission=trip).first()
        if not receipt:
            if pdf:return Response({'detail':'Aucun justificatif signé.'},status=404)
            return Response({'receipt':None,'consent':CONSENT})
        if not pdf:return Response({'receipt':receipt_data(receipt),'consent':CONSENT})
        response=HttpResponse(render_pdf(receipt),content_type='application/pdf')
        response['Content-Disposition']=f'attachment; filename="livraison-{receipt.pk}.pdf"'
        response['X-Content-Type-Options']='nosniff'
        services.audit(self.org,request.user,'receipt-download',receipt)
        return response

    def post(self,request,pk,pdf=False):
        if pdf:raise ValidationError('Utilisez le formulaire de signature.')
        if self.member.role not in ('owner','admin','operations','driver'):raise PermissionDenied()
        m.Organization.objects.select_for_update().get(pk=self.org.pk)
        trip=get_object_or_404(self.queryset('missions').select_for_update(of=('self',)),pk=pk)
        if trip.status!='completed':raise ValidationError('Clôturez la mission avant de faire signer le destinataire.')
        if m.DeliveryReceipt.objects.filter(organization=self.org,mission=trip).exists():
            return Response({'detail':'Cette livraison est déjà signée. Le justificatif est conservé sans modification.'},status=409)
        name=request.data.get('recipient_name');notes=request.data.get('reservations','')
        if not isinstance(name,str) or not 2<=len(name.strip())<=150 or not isinstance(notes,str) or len(notes)>5000:
            raise ValidationError('Nom du destinataire ou réserves invalides.')
        if request.data.get('consent') is not True:raise ValidationError('Le destinataire doit confirmer son accord avant de signer.')
        signed_at=timezone.now()
        receipt=m.DeliveryReceipt(organization=self.org,mission=trip,recipient_name=name.strip(),reservations=notes.strip(),
            signature=strokes(request.data.get('signature')),recorded_by=request.user,signed_at=signed_at)
        receipt.snapshot={
            'receipt_id':str(receipt.pk),'organization_id':str(self.org.pk),'company':self.org.name,
            'mission_id':str(trip.pk),'reference':trip.reference,'origin':trip.origin,'destination':trip.destination,
            'customer':trip.order.customer.name if trip.order_id else '',
            'vehicle':trip.vehicle.plate,'driver':trip.driver.name,'completed_at':trip.completed_at.isoformat(),
            'loaded_quantity':str(trip.loaded_quantity),'delivered_quantity':str(trip.delivered_quantity),
            'unit':trip.order.unit if trip.order_id else trip.vehicle.capacity_unit,
            'delivery_note':trip.delivery_note,'recipient_name':receipt.recipient_name,'reservations':receipt.reservations,
            'signed_at':signed_at.isoformat(),'recorded_by':request.user.nom,'consent':CONSENT,
            'signature':receipt.signature,
        }
        receipt.digest=hashlib.sha256(json.dumps(receipt.snapshot,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        receipt.full_clean();receipt.save()
        services.audit(self.org,request.user,'receipt-sign',receipt,mission=str(trip.pk),digest=receipt.digest)
        return Response({'receipt':receipt_data(receipt),'consent':CONSENT},status=201)


def render_pdf(receipt):
    import reportlab
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,Flowable,KeepTogether
    fonts=Path(reportlab.__file__).parent/'fonts'
    if 'TransitSans' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('TransitSans',str(fonts/'Vera.ttf')))
        pdfmetrics.registerFont(TTFont('TransitSans-Bold',str(fonts/'VeraBd.ttf')))
        pdfmetrics.registerFontFamily('TransitSans',normal='TransitSans',bold='TransitSans-Bold')
    styles=getSampleStyleSheet()
    for name in ('Normal','BodyText','Title','Heading2'):
        styles[name].fontName='TransitSans'
    styles['Title'].fontSize=24;styles['Title'].leading=30;styles['Title'].textColor=colors.HexColor('#103e37')
    styles['BodyText'].fontSize=9;styles['BodyText'].leading=14
    small=ParagraphStyle('Small',parent=styles['BodyText'],fontSize=7,leading=10,textColor=colors.HexColor('#586a62'))
    def text(value,style=None):return Paragraph(escape(str(value)).replace('\n','<br/>'),style or styles['BodyText'])
    def moment(value):return datetime.fromisoformat(value).strftime('%d/%m/%Y à %H:%M:%S')
    snapshot=receipt.snapshot
    class Signature(Flowable):
        def __init__(self):
            super().__init__()
            self.width=430;self.height=143
        def draw(self):
            self.canv.setStrokeColor(colors.HexColor('#173f38'));self.canv.setLineWidth(1.5)
            for stroke in receipt.signature:
                path=self.canv.beginPath();path.moveTo(stroke[0][0]*self.width/600,self.height-stroke[0][1]*self.height/200)
                for x,y in stroke[1:]:path.lineTo(x*self.width/600,self.height-y*self.height/200)
                self.canv.drawPath(path)
    rows=[]
    for label,key in [('Entreprise','company'),('Mission','reference'),('Client','customer'),('Départ','origin'),('Destination','destination'),('Véhicule','vehicle'),('Chauffeur','driver'),('Quantité chargée','loaded_quantity'),('Quantité livrée','delivered_quantity'),('Unité','unit'),('Livraison terminée (UTC)','completed_at')]:
        if snapshot.get(key):rows.append([text(label),text(moment(snapshot[key]) if key=='completed_at' else snapshot[key])])
    table=Table(rows,colWidths=[170,325],hAlign='LEFT')
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#edf4ef')),('LEFTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#dae4dc'))]))
    story=[text('TransitFlow',styles['Title']),text('JUSTIFICATIF DE LIVRAISON',styles['Heading2']),text('Document '+str(receipt.pk),small),Spacer(1,16),table,Spacer(1,16)]
    for title,key in [('Bilan de livraison','delivery_note'),('Réserves du destinataire','reservations')]:
        story.extend([text(title,styles['Heading2']),text(snapshot.get(key) or 'Aucune réserve indiquée.'),Spacer(1,10)])
    story.append(KeepTogether([text('Signature du destinataire',styles['Heading2']),text(receipt.recipient_name),text(snapshot['consent']),Signature(),text('Enregistrée le '+moment(snapshot['signed_at'])+' (UTC)',small)]))
    story.extend([Spacer(1,12),text('Empreinte SHA-256 : '+receipt.digest,small),text('Signature manuscrite capturée dans TransitFlow. Ce document ne constitue pas une signature électronique qualifiée.',small)])
    output=io.BytesIO()
    def footer(canvas,doc):
        canvas.setFont('TransitSans',7);canvas.setFillColor(colors.HexColor('#586a62'))
        canvas.drawString(42,25,'TransitFlow | Justificatif privé');canvas.drawRightString(553,25,str(doc.page))
    SimpleDocTemplate(output,pagesize=(595,842),rightMargin=50,leftMargin=50,topMargin=42,bottomMargin=45,
        title='Justificatif de livraison '+snapshot['reference'],author=snapshot['company']).build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
