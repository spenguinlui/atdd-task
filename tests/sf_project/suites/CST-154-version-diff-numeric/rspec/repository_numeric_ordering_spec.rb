# frozen_string_literal: true
#
# CST-154 Repository numeric ordering acceptance tests
#
# Place into the sf_project repo at:
#   spec/domains/project_management/project/repositories/numeric_ordering_spec.rb
#
# Tests cover the two repository defects:
#   - find_previous_approved_version: string '<' comparison breaks across digit boundaries
#   - find_newest_approved_version: should sort by numeric version_serial_number, not submitted_at

require 'rails_helper'

RSpec.describe ProjectManagement::Project::Repositories::Project, 'numeric version ordering (CST-154)' do
  let(:repo) { described_class.new }
  let!(:project) do
    create(:project_management_project, serial_number: 'RT020040')
  end

  def make_version(serial:, status:, submitted_at: nil)
    create(
      :project_management_project_version,
      project_id: project.id,
      version_serial_number: serial,
      status: status,
      submitted_at: submitted_at,
    )
  end

  describe '#find_previous_approved_version' do
    context 'S2-edge: 1..10 all approved, target = 10 (RT020040 reproduction)' do
      before do
        (1..10).each { |n| make_version(serial: n.to_s, status: 'approved') }
      end

      it 'returns version 9 (numeric predecessor), not the lexicographic max under 10' do
        result = repo.find_previous_approved_version(
          serial_number: 'RT020040', version_serial_number: '10',
        )
        expect(result).not_to be_nil
        expect(result.version_serial_number).to eq('9')
      end
    end

    context 'S3-edge: 1, 50, 99, 100 all approved, target = 100' do
      before do
        %w[1 50 99 100].each { |n| make_version(serial: n, status: 'approved') }
      end

      it 'returns 99' do
        result = repo.find_previous_approved_version(
          serial_number: 'RT020040', version_serial_number: '100',
        )
        expect(result.version_serial_number).to eq('99')
      end
    end

    context 'S4-edge: target is the only / first version' do
      before { make_version(serial: '1', status: 'approved') }

      it 'returns nil (no previous approved) without raising' do
        expect {
          @result = repo.find_previous_approved_version(
            serial_number: 'RT020040', version_serial_number: '1',
          )
        }.not_to raise_error
        expect(@result).to be_nil
      end
    end

    context 'S5-edge: canceled mid-version is skipped, numeric ordering still wins' do
      before do
        make_version(serial: '8', status: 'approved')
        make_version(serial: '9', status: 'canceled')
        make_version(serial: '10', status: 'approved')
      end

      it 'returns 8 (skips canceled 9)' do
        result = repo.find_previous_approved_version(
          serial_number: 'RT020040', version_serial_number: '10',
        )
        expect(result.version_serial_number).to eq('8')
      end
    end

    context 'regression guard: previous lexicographic-only ordering would pick wrong version' do
      # If implementation still uses string '<' comparison, target '2' would
      # incorrectly include '10', '11' as "less than '2'" -- this would yield '11'
      # as previous. We assert the correct numeric answer instead.
      before do
        %w[1 2 10 11].each { |n| make_version(serial: n, status: 'approved') }
      end

      it 'returns 1 for target 2 (numeric), not 11 or 10' do
        result = repo.find_previous_approved_version(
          serial_number: 'RT020040', version_serial_number: '2',
        )
        expect(result.version_serial_number).to eq('1')
      end
    end
  end

  describe '#find_newest_approved_version (S8-regression)' do
    context 'when submitted_at order disagrees with version_serial_number numeric order' do
      before do
        # version 5 was submitted earlier, version 3 was submitted later.
        # Old implementation sorted by submitted_at -> would pick 3.
        # New implementation sorts by numeric version_serial_number -> picks 5.
        make_version(serial: '3', status: 'approved', submitted_at: Time.zone.parse('2026-05-05 10:00'))
        make_version(serial: '5', status: 'approved', submitted_at: Time.zone.parse('2026-05-01 10:00'))
      end

      it 'returns version 5 (max numeric), not 3 (latest submitted_at)' do
        result = repo.find_newest_approved_version(serial_number: 'RT020040')
        expect(result.version_serial_number).to eq('5')
      end
    end

    context 'across digit boundary: 9 vs 10 both approved' do
      before do
        make_version(serial: '9', status: 'approved')
        make_version(serial: '10', status: 'approved')
      end

      it 'returns 10 (numeric max), not 9 (lexicographic max)' do
        result = repo.find_newest_approved_version(serial_number: 'RT020040')
        expect(result.version_serial_number).to eq('10')
      end
    end
  end
end
