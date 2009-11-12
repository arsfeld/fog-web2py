def email(sender,to,subject,message):
    import smtplib
    fromaddr=sender
    if type(to)==type([]): toaddrs=to
    else: toaddrs=[to]
    msg="From: %s\r\nTo: %s\r\nSubject: %s\r\n\r\n%s"%(fromaddr,\
        ", ".join(toaddrs),subject,message)
    server = smtplib.SMTP('localhost') 
    server.sendmail(fromaddr, toaddrs, msg)
    server.quit()
