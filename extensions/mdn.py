import markdown as markdown_module

def markdown(text):
  return markdown_module.markdown(text, 
                                  ['codehilite', 'extra', 'nl2br'])

def init(instance):
  instance.registerUtil('markdown', markdown)
