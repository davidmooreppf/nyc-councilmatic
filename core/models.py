from django.db import models
from datetime import datetime
import pytz


class Person(models.Model):
	ocd_id = models.CharField(max_length=100, unique=True)
	name = models.CharField(max_length=100)
	headshot = models.CharField(max_length=255, blank=True)
	source_url = models.CharField(max_length=255)
	source_note = models.CharField(max_length=255, blank=True)
	slug = models.CharField(max_length=255, unique=True)

	def __str__(self):
		return self.name

	@property
	def council_seat(self):
		return self.memberships.filter(organization__ocd_id='ocd-organization/389257d3-aefe-42df-b3a2-a0d56d0ea731').first().post.label

	@property
	def is_speaker(self):
		return True if self.memberships.filter(role='Speaker').first() else False	

	@property
	def headshot_url(self):
		if self.headshot:
			return '/static/images/' + self.ocd_id + ".jpg"
		else:
			return '/static/images/headshot_placeholder.png'

class Bill(models.Model):
	ocd_id = models.CharField(max_length=100, unique=True)
	description = models.TextField()
	identifier = models.CharField(max_length=50)
	bill_type = models.CharField(max_length=50)
	classification = models.CharField(max_length=100)
	date_created = models.DateTimeField(default=None)
	date_updated = models.DateTimeField(default=None, null=True)
	source_url = models.CharField(max_length=255)
	source_note = models.CharField(max_length=255, blank=True)
	from_organization = models.ForeignKey('Organization', related_name='bills', null=True)
	full_text = models.TextField(blank=True)
	last_action_date = models.DateTimeField(default=None, null=True)
	legislative_session = models.ForeignKey('LegislativeSession', related_name='bills', null=True)
	slug = models.CharField(max_length=255, unique=True)

	def __str__(self):
		return self.friendly_name

	@property
	def controlling_body(self):
		if self.current_action:
			related_orgs = self.current_action.related_entities.filter(entity_type='organization').all()
			if related_orgs:
				controlling_bodies = [Organization.objects.all().filter(ocd_id=org.organization_ocd_id).first() for org in related_orgs]
				return controlling_bodies
			else:
				return [self.current_action.organization]
		else:
			return None

	@property
	def last_action_org(self):
		return self.current_action.organization if self.current_action else None

	@property
	def current_action(self):
		return self.actions.all().order_by('-order').first() if self.actions.all() else None

	@property
	def friendly_name(self):
		nums_only = self.identifier.split(' ')[-1]
		return self.bill_type+' '+nums_only

	@property
	def primary_sponsor(self):
		return self.sponsorships.filter(is_primary=True).first()

	@property
	def is_stale(self):
		# stale = no action for 2 months
		eastern = pytz.timezone('US/Eastern')
		if self.current_action:
			timediff = datetime.now().replace(tzinfo=eastern) - self.current_action.date
			return (timediff.days > 60)
		else:
			return True

	@property
	def is_passed(self):
		if self.actions:
			return ('Signed Into Law by Mayor' in [a.description for a in self.actions.all()])
		else:
			return False

	@property
	def is_approved(self):
		if self.actions:
			return any(['Approved' in a.description for a in self.actions.all()])
		else:
			return False

	@property
	def inferred_status(self):
		if self.is_passed:
			return 'Passed'
		elif self.is_approved:
			return 'Approved'
		elif self.is_stale:
			return 'Stale'
		else:
			return 'Active'


	def get_last_action_date(self):
		return self.actions.all().order_by('-order').first().date if self.actions.all() else None

class Organization(models.Model):
	ocd_id = models.CharField(max_length=100, unique=True)
	name = models.CharField(max_length=255)
	classification = models.CharField(max_length=255, null=True)
	parent = models.ForeignKey('self', related_name='children', null=True)
	slug = models.CharField(max_length=255, unique=True)

	def __str__(self):
		return self.name

	@classmethod
	def committees(cls):
		return cls.objects.filter(classification='committee').order_by('name').all()

	@property
	def recent_activity(self):
		return self.actions.order_by('-date', '-bill__identifier', '-order') if self.actions.all() else None

	@property
	def chairs(self):
		return self.memberships.filter(role='CHAIRPERSON')

	@property
	def link_html(self):
		# make link to committee if committee
		if self.classification == 'committee':
			return '<a href="/committee/'+self.slug+'">'+self.name+'</a>'
		# link to the council members page if its the council
		if self.classification == 'legislature':
			return '<a href="/council-members">'+self.name+'</a>'
		# just return text if executive
		else:
			return self.name

class Action(models.Model):
	date = models.DateTimeField(default=None)
	classification = models.CharField(max_length=100)
	description = models.TextField(blank=True)
	organization = models.ForeignKey('Organization', related_name='actions', null=True)
	bill = models.ForeignKey('Bill', related_name='actions', null=True)
	order = models.IntegerField()

	@property 
	def label(self):
		c = self.classification
		
		if c == 'committee-passage': return 'success'
		if c == 'passage': return 'success'
		if c == 'executive-signature': return 'success'
		if c == 'amendment-passage': return 'success'

		if c == 'amendment-introduction': return 'info'
		if c == 'introduction': return 'info'
		if c == 'committee-referral': return 'info'
		if c == 'filing': return 'info'
		if c == 'executive-received': return 'info'

		if c == 'deferred': return 'primary'

		else: return 'info'

class ActionRelatedEntity(models.Model):
	action = models.ForeignKey('Action', related_name='related_entities')
	entity_type = models.CharField(max_length=100)
	entity_name = models.CharField(max_length=255)
	organization_ocd_id = models.CharField(max_length=100, blank=True)
	person_ocd_id = models.CharField(max_length=100, blank=True)

class Post(models.Model):
	ocd_id = models.CharField(max_length=100, unique=True)
	label = models.CharField(max_length=255)
	role = models.CharField(max_length=255)
	organization = models.ForeignKey('Organization', related_name='posts')

class Membership(models.Model):
	organization = models.ForeignKey('Organization', related_name='memberships')
	person = models.ForeignKey('Person', related_name='memberships')
	post = models.ForeignKey('Post', related_name='memberships', null=True)
	label = models.CharField(max_length=255, blank=True)
	role = models.CharField(max_length=255, blank=True)
	start_date = models.DateField(default=None, null=True)
	end_date = models.DateField(default=None, null=True)

class Sponsorship(models.Model):
	bill = models.ForeignKey('Bill', related_name='sponsorships')
	person = models.ForeignKey('Person', related_name='sponsorships')
	classification = models.CharField(max_length=255)
	is_primary = models.BooleanField(default=False)

class Event(models.Model):
	ocd_id = models.CharField(max_length=100, unique=True)
	name = models.CharField(max_length=255)
	description = models.TextField()
	classification = models.CharField(max_length=100)
	start_time = models.DateTimeField()
	end_time = models.DateTimeField(null=True)
	all_day = models.BooleanField(default=False)
	status = models.CharField(max_length=100)
	location_name = models.CharField(max_length=255)
	location_url = models.CharField(max_length=255, blank=True)
	source_url = models.CharField(max_length=255)
	source_note = models.CharField(max_length=255, blank=True)

class EventParticipant(models.Model):
	event = models.ForeignKey('Event', related_name='participants')
	note = models.TextField()
	entity_name = models.CharField(max_length=255)
	entity_type = models.CharField(max_length=100)

class Document(models.Model):
	note = models.TextField()
	url = models.TextField()

class BillDocument(models.Model):
	bill = models.ForeignKey('Bill', related_name='documents')
	document = models.ForeignKey('Document', related_name='bills')

class EventDocument(models.Model):
	event = models.ForeignKey('Event', related_name='documents')
	document = models.ForeignKey('Document', related_name='events')

class LegislativeSession(models.Model):
	identifier = models.CharField(max_length=255)
	jurisdiction_ocd_id = models.CharField(max_length=255)
	name = models.CharField(max_length=255)
