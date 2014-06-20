from twisted.internet.protocol import Protocol, Factory
from twisted.internet.endpoints import TCP4ClientEndpoint, connectProtocol
from twisted.internet import tksupport, reactor, protocol
from Tkinter import *
import sys



class UI:

    def __init__(self, master):

        # set up start of screen
        self.root = master

        # set up frame
        self.frame = Frame(self.root, width=250, height=325)
        self.frame.pack_propagate(0)
        self.frame.pack()

        # set up Message box
        self.message_box = Text(self.frame, height=15, width=25, bg='white', bd=5, relief=RIDGE, state='disabled')
        self.message_box.pack(side=TOP)

        # set up entry box
        self.entry_box = Text(self.frame, height=2, width=25, bg='white', bd=5, relief=RIDGE)
        self.entry_box.bind('<Return>', self.send_message)
        self.entry_box.pack(side=BOTTOM)

        # set up label
        self.label = Label(self.frame, text='Enter a message')
        self.label.pack(side=BOTTOM)


    def send_message(self, event):

        message = self.entry_box.get(1.0, END)
        self.entry_box.delete(1.0, END)   

        point = TCP4ClientEndpoint(reactor, "localhost", int(sys.argv[2]))
        d = connectProtocol(point, Greeter())

        def gotProtocol(p):
            p.sendMessage('hello')
            reactor.callLater(1, p.transport.loseConnection)

        d.addCallback(gotProtocol)

class Greeter(Protocol):
    def sendMessage(self, msg):
        self.transport.write(msg)

class GreeterFactory(Factory):
    def buildProtocol(self, addr):
        return Greeter()

class Listen(protocol.Protocol):

    def dataReceived(self, data):
        print 'received!'

        message = str(data)

        ui.message_box.config(state='normal')
        ui.message_box.insert(END, '%s\n' %(message))
        ui.message_box.config(state='disabled')

# start UI        
root = Tk()
root.tk_bisque()
root.title('Client Messager')
root.resizable(width=FALSE, height=FALSE)
ui = UI(root)
tksupport.install(root)

# start listneing
factory = protocol.ServerFactory()
factory.protocol = Listen
reactor.listenTCP(int(sys.argv[1]),factory)
reactor.run()