# -*- coding: utf-8 -*-
from django.utils.translation import ugettext_lazy as _       ##Tranlators

##############################################################################################
def getPage(request):
    '''
        Return a page or raise a 404 error
    '''
    import cPickle
    from django.http import Http404, HttpResponseRedirect
    try:
        return cPickle.loads(request.session['page'])
    except:
        return HttpResponseRedirect('/accounts/register/?next=editpage')

##############################################################################################
def updatePageCacheAndSession(request, page):

    ##Update session
    page.save()        
    import cPickle
    request.session['page'] = cPickle.dumps(page) 

    ##Flush cache
    from django.core.cache import cache
    cache.delete(page.user.username)
    cache.delete(page.domain)   

##############################################################################################
def showpage(request, username=None):
    '''
        return requested page to the visitor
    '''
    from django.shortcuts import render_to_response, get_object_or_404
    from django.template import RequestContext  
    from django.core.cache import cache 
    from django.conf import settings
    from pages.models import Page
    
    if username is None:
        domain = request.get_host()

        if domain in settings.MAIN_HOST.split():
            websitetemplate = cache.get('websitetemplate')            

            if not websitetemplate:
                from django.conf import settings
                websitetemplate =  render_to_response('pages/website.html',
                                     {
                                        'price':settings.PAGE_MONTHLY_PRICE,
                                        'facebook':settings.ELDON_FACEBOOK,
                                        'twitter':settings.ELDON_TWITTER,
                                        'blog':settings.ELDON_BLOG,
                                        'google_plus':settings.ELDON_GOOGLEPLUS,
                                        'youtube':settings.ELDON_YOUTUBE,
                                        'pinterest':settings.ELDON_PINTEREST,                                
                                        'fax':settings.ELDON_FAX,
                                        'phone':settings.ELDON_PHONE,
                                        'googlemap': settings.ELDON_GOOGLEMAP,
                                                                                                                                                                                                                                        
                                        'support': settings.ELDON_SUPPORT_EMAIL,
                                        'press': settings.ELDON_PRESS_EMAIL,
                                        'general': settings.ELDON_GENERAL_EMAIL,                                        

                                     },
                                     context_instance=RequestContext(request))
                cache.set('websitetemplate',websitetemplate)              
            return websitetemplate 
            
        else:
            page = cache.get(domain)
            if not page:              
                page = get_object_or_404(Page.objects.prefetch_related('photo_set', 'pdf_set','field_set'),
                                         domain=domain , is_active=True)
                cache.set(domain, page)                
    else:
        page = cache.get(username)
        if not page:
            page = get_object_or_404(Page.objects.prefetch_related('photo_set', 'pdf_set','field_set'), user__username=username , is_active=True)
            cache.set(username, page)
        
    ### log for analytics    
    import datetime
    from pages.models import Analytic, VisitorIP
    
    visitorip = VisitorIP.objects.filter(pageseen=page, ip=request.META['REMOTE_ADDR']).exists()
    if not visitorip:
        visitorip = VisitorIP(pageseen=page, ip=request.META['REMOTE_ADDR'])
        visitorip.save()
        try:
            analytic = Analytic.objects.get(page=page, date=datetime.date.today())
            analytic.visit = analytic.visit+1   ###We create a new entry for each page each day
        except Analytic.DoesNotExist:
            analytic = Analytic(page=page, date=datetime.date.today(), visit=1)
        
        analytic.save()           

    return render_to_response('pages/showpage.html',
                             {
                                'page':page,
                                'path':request.build_absolute_uri(),
                             },
                             context_instance=RequestContext(request))

##############################################################################################
from django.contrib.auth.decorators import login_required
@login_required
def editpage(request):
    '''
        Allow user to edit his page
    '''
    from django.shortcuts import render_to_response
    from django.template import RequestContext
    from django.conf import settings

    from django.middleware.csrf import get_token ##For ajaxuploader
    
    page = getPage(request)

    return render_to_response('pages/editpage.html',
                             {
                                'page':page,
                                'csrf_token': get_token(request),

                                'yearlyprice': settings.PAGE_MONTHLY_PRICE*12,
                                'sixmonthprice': settings.PAGE_MONTHLY_PRICE*6,
                                'monthlyprice': settings.PAGE_MONTHLY_PRICE,
                                'max_fields': settings.MAX_FIELDS,
                             },
                             context_instance=RequestContext(request))    

##############################################################################################
def validateData(field, value):
    '''
        Validate editable elements on the page
    '''
    from pages.forms import DataForm    
    
    allowed_fields = {'name':0,'short_description':0,'logo_x':0,'logo_y':0,'name_size':0, 'short_description_size':0, 'name_align':0,'name_x':0,'name_y':0,
                      'name_color':0,'box_color':0,'box_y':0,'box_x':0, 'is_logo_visible':0, 'is_name_visible':0, 'description':0,
                      'is_map_visible':0, 'map_x':0, 'map_y':0, 'box_size':0, 'zoom':0, 'font':0}
    try:
        is_allowed = allowed_fields[field]
    except:
        return False
    
    form = DataForm({field:value})
    return form

##############################################################################################
def uploaddata(request):
    '''
        Allow user to edit his page informations
    '''
    from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed
    
    if request.method == 'POST' and request.is_ajax():
        page = getPage(request)  
        try:
            field = request.POST['field']
            value = request.POST['value']
            if value == 'false':
                value = False
            form = validateData(field, value)
        except:
            return HttpResponseBadRequest(u'%s' % _('An error occured'))
            
        if form.is_valid():
            setattr(page, field, value)
        else:
            errors = ''
            for error in form.errors.values():
                errors = errors+error[0]
            return HttpResponseBadRequest(errors)         
            
        try:         ## IF THERE IS OPTIONNAL PARAMETERS SAVE IT AND FAIL SILENTLY
            optionalfield = request.POST['optionalfield']
            optionalvalue = request.POST['optionalvalue']
            optional_form = validateData(optionalfield, optionalvalue)     
            if optional_form.is_valid():              
                setattr(page, optionalfield, optionalvalue)                       
        except:
            pass            
        
        ##Flush cache and update session
        updatePageCacheAndSession(request,page)
 
        return HttpResponse(u'%s' % _('Saved'))
        
    return HttpResponseNotAllowed(['POST'])
     
##############################################################################################
def uploadfile(request):
    '''
        Initialize Ajax File Uploader
    '''
    from ajaxuploader.views import AjaxFileUploader
    from pages.ajaxupload import CustomStorageUploadBackend
    from django.http import HttpResponseBadRequest 
    
    directory = request.GET['directory']
    directory_allowed = {'background':0, 'photo':0, 'pdf':0, 'logo':0}
    try:
        directory_allowed[directory]
    except:
        return HttpResponseBadRequest()
    
    uploaderresponse = AjaxFileUploader(backend=CustomStorageUploadBackend, uploaddir='uploads/'+directory+'/')
    return uploaderresponse._ajax_upload(request)

##############################################################################################
def uploadfilecomplete(request):
    '''
        After uploaded file, save it to db
    '''    
    from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed   
    from pages.models import Photo, Pdf
    from django.conf import settings        
     
    if request.method == 'POST' and request.is_ajax():
        page = getPage(request) 
        filetype_allowed = {'background':0, 'logo':0, 'photo':0, 'pdf':0}
        try: 
            filename = request.POST['filename']
            filetype = request.POST['type']
            filetype_allowed[filetype]
        except:
            return HttpResponseBadRequest(u'%s' % _('An error occured'))
        
        if filetype == 'background' or filetype == 'logo':
            setattr(page, filetype, 'uploads/'+filetype+'/'+filename)        
        else:
            if filetype == 'photo':
                if page.photo_set.count() >= settings.MAX_PHOTO:
                    return HttpResponseBadRequest(u'%s' % _('You cant save more than %s pictures') % settings.MAX_PHOTO)
                photofile = Photo(page=page, photo='uploads/'+filetype+'/'+filename)
                page.photo_set.add(photofile)
                photofile.thumbnail.url
            elif filetype == 'pdf':
                if page.pdf_set.count() >= settings.MAX_PDF:
                    return HttpResponseBadRequest(u'%s' % _('You cant save more than %s docs') % settings.MAX_PDF)            
                try: 
                    original_filename = request.POST['original_filename']
                except:
                    original_filename = ''
                pdffile = Pdf(page=page, pdf='uploads/'+filetype+'/'+filename, name=original_filename)
                page.pdf_set.add(pdffile) 
        
        ##Flush cache and update session
        updatePageCacheAndSession(request,page)
        
        return HttpResponse(u'%s' % _('Saved'))
    
    return HttpResponseNotAllowed(['POST'])

##############################################################################################
def validateField(field):
    '''
        Validate fields elements
    '''
    from pages.forms import FieldForm

    form = FieldForm({'field':field})
    if form.is_valid():
        return True
    else:
        return False   

##############################################################################################
def uploadfields(request):
    '''
        Create or update fields  
    '''    
    from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed
    from django.utils import simplejson
    from pages.models import Field
    from django.conf import settings    
    
    if request.method == 'POST' and request.is_ajax():     
        page = getPage(request)
        try: 
            fields = request.POST['fields']
        except:
            return HttpResponseBadRequest(u'%s' % _('An error occured'))

        fields = simplejson.loads(fields)
        
        if len(fields) >= settings.MAX_FIELDS:
            return HttpResponseBadRequest(u'%s' % _('You cant save more than %s fields') % str(settings.MAX_FIELDS-4))

        try:
            page.field_set.all().delete()
        except:
            pass
            
        fields_tobe_saved = [] 
        for field in fields:
            form_is_valid = validateField(field[0])
            if form_is_valid:
                fields_tobe_saved.append(Field(page=page, field=field[0], position=field[1]))
            
        Field.objects.bulk_create(fields_tobe_saved)

        ##Flush cache and update session
        updatePageCacheAndSession(request,page)               
        
        return HttpResponse(u'%s' % _('Saved'))

    return HttpResponseNotAllowed(['POST'])

##############################################################################################
def deletefile(request):
    '''
        Delete file
    '''   
    if request.method == 'POST' and request.is_ajax():     
        from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed        
        page = getPage(request)
        try: 
            file_id = request.POST['file_id']
            file_type = request.POST['file_type']
        except:
            return HttpResponseBadRequest(u'%s' % _('An error occured'))

        if file_type == 'photo':
            try:
                thefile = page.photo_set.filter(id=file_id)[0]
            except:
                try:
                    thefile = page.photo_set.filter(photo=file_id)[0]
                except:
                    return HttpResponseBadRequest(u'%s' % _('An error occured'))
        elif file_type == 'pdf':
            try:
                thefile = page.pdf_set.filter(id=file_id)[0]
            except:
                try:
                    thefile = page.pdf_set.filter(pdf=file_id)[0]
                except:
                    return HttpResponseBadRequest(u'%s' % _('An error occured'))
        else:
            return HttpResponseBadRequest(u'%s' % _('An error occured'))            

        thefile.delete()
        
        ##Update session and flush cache
        updatePageCacheAndSession(request,page)                
        
        return HttpResponse(u'%s' % _('Deleted'))
    return HttpResponseNotAllowed(['POST'])        
                
##############################################################################################          
def getstats(request, period):
    '''
        return stats
    '''     
    import datetime, time
    from django.utils import simplejson
    from pages.models import Analytic
    from django.http import HttpResponse, HttpResponseNotAllowed

    if request.method == 'GET' and request.is_ajax():    
        page = getPage(request)       
            
        if period == 'year':
            date = datetime.date.today()-datetime.timedelta(366)
        elif period == 'month':
            date = datetime.date.today()-datetime.timedelta(31)
        elif period == 'week':
            date = datetime.date.today()-datetime.timedelta(7)
        else:
            date = datetime.date.today()    

        try:
            result = request.session[period]
        except KeyError:
            if period == 'today':
                result = Analytic.objects.filter(page=page, date=date).order_by('date')
            else:
                result = Analytic.objects.filter(page=page, date__gte=date).order_by('date')
            request.session[period] = result
                            
        stats = []
        total = 0
        for elem in result:
            data = [] 
            data.append(int(time.mktime(elem.date.timetuple())*1000))
            data.append(elem.visit)
            stats.append(data)
            total = total+elem.visit

        to_json = {
        "data": stats,
        "total": total
        }
        return HttpResponse(simplejson.dumps(to_json), mimetype='application/json')                       
    return HttpResponseNotAllowed(['GET'])            
        
##############################################################################################        
def domainvalid(request, domainname, tld=None, domaintype='new'):
    '''
      Check for domain name availability
    '''        
    from django.conf import settings      
    from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed  
    from pages.models import Page  
    from pages.ovh import domainCheck
    if not tld :
        domain = domainname
    else:
        domain = domainname+'.'+tld
      
    result = domainCheck(settings.OVH_LOGIN, settings.OVH_MDP, domain)

    domain_exist = Page.objects.filter(domain=domain).exists()
      
    if domain_exist:
        return HttpResponseBadRequest(u'%s' % _('This domain is already registered by another user'))

    if domaintype == 'new':
        if result['item'][0]['value'] == True:
          return HttpResponse(u'%s' % _('Great! This domain is free and offered to you'))
        else:
          return HttpResponseBadRequest(u'%s' % _('This domain is not available'))
    elif domaintype == 'own':
        if result['item'][1]['value'] == True:
          return HttpResponse(u'%s' % _('Ce domaine est transferable'))
        else:
          return HttpResponseBadRequest(u'%s' % _('Ce domaine nest pas transferable car il est disponible'))
    else:
        return HttpResponseBadRequest(u'%s' % _('An error occured when processing'))
        
################################################################  
def processcheckout(request):
    '''
        Paypal checkout
    '''    
    from django.conf import settings      
    from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed  
    from pages.models import Page, Bill
        
    if request.method == 'POST' and request.is_ajax():
    
        page = getPage(request)    
        ####GET THE KEYS
        try:
            charges = request.POST['charges']
            domainname = request.POST['domainname']
            domainoption = request.POST['domainoption']
        except:
            return HttpResponseBadRequest(u'%s' % _('an error occured when processing checkout'))

        if charges == 'yearly':       ###########################CHECK CONFORMITY OF CHARGES    
            item_name = _("EldonPage suscribtion for 1 year")
            amount = settings.PAGE_MONTHLY_PRICE * 12
            t3 = "Y"
            p3 = 1
        elif charges == 'sixmonth':    
            item_name = _("EldonPage suscribtion for six month")
            amount = settings.PAGE_MONTHLY_PRICE * 6
            t3 = "M"
            p3 = 6
        elif charges == 'monthly':    
            item_name = _("EldonPage suscribtion for 1 monthly")
            amount = settings.PAGE_MONTHLY_PRICE
            t3 = "M"
            p3 = 1        
        else:
            return HttpResponseBadRequest(u'%s' % _('an error occured when processing checkout'))

        import uuid ###########################CREATE THE BILL
        invoice = str(uuid.uuid1())
        
        #### WE CHECK FIRST IF USER HAS ALREADY CREATED A BILL
        try:
            bill = Bill.objects.get(page=page, invoice_type='creation')
            bill.amount = amount
            bill.invoice = invoice
            bill.domain = domainname
            bill.save()
        except Bill.DoesNotExist:
            bill = Bill(page=page, amount=amount, invoice=invoice, domain=domainname)
            bill.save()
        except:
            return HttpResponse(u'%s' % _('an error occured when processing checkout'))
        
        from paypal.standard.forms import PayPalPaymentsForm
        paypal = {
              "business":settings.PAYPAL_RECEIVER_EMAIL, #settings.PAYPAL_RECEIVER_EMAIL,
              "item_name": item_name,
              "currency_code": 'USD',
              "a3": amount,                      # monthly price 
              "p3": p3,                           # duration of each unit (depends on unit)
              "t3": t3,                         # duration unit ("M for Month")              
              "src": "1",                        # make payments recur              
              "sra": "1",                        # reattempt payment on payment error
              "no_note": "1",                    # remove extra notes (optional)              
              "invoice": invoice,
              "cmd": "_xclick-subscriptions",

              'custom': page.id,
              "notify_url": "http://eldonpage.com/sdf5f2sf/sdf56sfd/sfsf6s3/sdfd3r23rs/csdc65/32w3cds/",
              "return_url": "http://eldonpage.com/editpage/",
              "cancel_return": "http://eldonpage.com/editpage/",
          }    
        form = PayPalPaymentsForm(initial=paypal)
        if settings.DEBUG:
            rendered_form = form.sandbox()
        else:
            rendered_form = form.render()    

        return HttpResponse(rendered_form)             

    return HttpResponseBadRequest(u'%s' % _('an error occured when processing checkout'))      


def email_to_manager(request):
    '''
        Send Email to pages manager
    '''
    if request.method == 'POST' and request.is_ajax():   
        from django.conf import settings
        from django.core.mail import send_mail
        from django.template.loader import get_template        
        from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed          
        from django.template import Context
        from pages.models import Page 

        try: 
            from_email = request.POST['from_email']
            message_content = request.POST['message_content']
            page = Page.objects.get(id=int(request.POST['pageid']))      
        except:
            return HttpResponseBadRequest(u'%s' % _('An error occureds'))

        from pages.forms import UserEmailForm

        form = UserEmailForm({'page':page.id, 'from_email':from_email, 'message_content':message_content})
        if not form.is_valid():
            return HttpResponseBadRequest(u'%s' % _('an error occured when sending email')) 

        form.save()
        plaintext = get_template('emails/emailtomanager.txt')
        
        d = Context({ 'message_content': message_content, 'from_email': from_email, 'username':page.user.username })

        subject, eldon_email, to = _('EldonPage | Someone sent you a message'), settings.DEFAULT_FROM_EMAIL, page.user.email
        
        message = plaintext.render(d)

        try:
            send_mail(subject, message , eldon_email, [to], fail_silently=False)
        except:
            return HttpResponseBadRequest(u'%s' % _('an error occured when sending email'))    
        return HttpResponse(u'%s' % _('message sent successfully'))

    return HttpResponseNotAllowed(['POST'])      
